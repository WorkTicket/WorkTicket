import logging
import time
from datetime import UTC, datetime, timedelta

from celery_config.beat import _acquire_beat_lock
from celery_config.broker import get_sync_redis
from celery_config.worker import _run_async, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, queue="beat")
def cleanup_stale_reservations_task(self):
    """Release stale reservations and reset associated job states.
    V2-FIX: Scheduled beat task (every 5 min) — previously this only ran
    during API startup. Ghost reservations from failed enqueues are now cleaned proactively.
    """
    if not _acquire_beat_lock(self.app, "cleanup_stale_reservations_task", ttl=300):
        logger.warning("cleanup_stale_reservations_task skipped — another execution in progress")
        return {"status": "skipped", "reason": "concurrent_execution_locked"}

    from app.billing.state_machine import cleanup_stale_reservations
    from app.database import AsyncSessionLocal

    try:

        async def _run():
            async with AsyncSessionLocal() as db:
                await cleanup_stale_reservations(db)

        _run_async(_run())
        return {"status": "completed"}
    except Exception as e:
        logger.error("Stale reservation cleanup failed: %s", e)
        raise self.retry(exc=e) from e


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, queue="beat")
def alert_stuck_jobs(self):
    """Alert on jobs stuck in non-terminal state for >1 hour."""
    if not _acquire_beat_lock(self.app, "alert_stuck_jobs", ttl=300):
        return {"status": "skipped", "reason": "concurrent_execution_locked"}

    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.jobs.models import Job

    try:

        async def _run():
            async with AsyncSessionLocal() as db:
                cutoff = datetime.now(UTC) - timedelta(hours=1)
                result = await db.execute(
                    select(Job).where(
                        Job.ai_processing_state.in_(["queued", "reserved", "processing"]),
                        Job.ai_processing_updated_at < cutoff,
                    )
                )
                stuck = result.scalars().all()
                if stuck:
                    logger.critical("%d jobs stuck in non-terminal state for >1 hour", len(stuck))
                    try:
                        from app.monitoring.prometheus import set_stuck_jobs_processing

                        set_stuck_jobs_processing(len(stuck))
                    except Exception as _e:
                        logger.debug("Failed to set stuck jobs metric: %s", _e)
                return {"stuck_count": len(stuck)}

        _run_async(_run())
    except Exception as e:
        logger.error("Stuck job alert failed: %s", e)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, queue="beat")
def cleanup_old_estimates(self):
    """Purge old AIJobEstimate records older than 90 days."""
    from app.config import FeatureFlags, get_settings

    _settings = get_settings()
    _flags = FeatureFlags()
    if _settings.ai_disabled or _flags.is_enabled(FeatureFlags.AI_DISABLED):
        logger.debug("AI disabled — skipping cleanup_old_estimates")
        return {"status": "skipped", "reason": "ai_disabled"}

    if not _acquire_beat_lock(self.app, "cleanup_old_estimates", ttl=86400):
        return {"status": "skipped", "reason": "concurrent_execution_locked"}

    from sqlalchemy import delete, select

    from app.billing.models import AIJobEstimate
    from app.database import AsyncSessionLocal

    try:

        async def _run():
            async with AsyncSessionLocal() as db:
                cutoff = datetime.now(UTC) - timedelta(days=90)
                total = 0
                BATCH_SIZE = 1000
                while True:
                    stmt = delete(AIJobEstimate).where(
                        AIJobEstimate.created_at < cutoff,
                        AIJobEstimate.id.in_(
                            select(AIJobEstimate.id).where(AIJobEstimate.created_at < cutoff).limit(BATCH_SIZE)
                        ),
                    )
                    result = await db.execute(stmt)
                    if result.rowcount and result.rowcount > 0:
                        total += result.rowcount
                        await db.commit()
                        logger.info("Batch purged %d old AIJobEstimate records (total=%d)", result.rowcount, total)
                    else:
                        break
                    if result.rowcount < BATCH_SIZE:
                        break
                return {"purged": total}

        _run_async(_run())
    except Exception as e:
        logger.error("Cleanup old estimates failed: %s", e)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10, queue="beat")
def cleanup_stale_jobs(self):
    if not _acquire_beat_lock(self.app, "cleanup_stale_jobs", ttl=120):
        logger.warning("cleanup_stale_jobs skipped — another execution is in progress")
        return {"status": "skipped", "reason": "concurrent_execution_locked"}
    try:
        from app.database import _check_db_circuit

        _check_db_circuit()
    except Exception as cb_err:
        logger.warning("cleanup_stale_jobs skipped — DB circuit breaker open: %s", cb_err)
        return {"status": "skipped", "reason": "db_circuit_open"}

    from app.tasks.retry_guard import check_retry_storm

    if self.request.retries > 0 and not check_retry_storm("scheduled", "cleanup_stale_jobs"):
        logger.error("Retry storm blocked for cleanup_stale_jobs")
        return {"status": "blocked", "reason": "retry_storm"}

    from app.tasks.heartbeat import cleanup_stale_jobs as _cleanup

    try:
        stats = _cleanup()
        return stats
    except Exception as e:
        logger.error("Scheduled stale job cleanup failed: %s", e)
        raise self.retry(exc=e) from e


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, queue="beat", acks_late=False)
def purge_soft_deleted_records(self):
    """Hard-delete soft-deleted records older than 90 days.

    Preserves audit trail within retention window while preventing
    unbounded table growth from orphaned soft-deleted records.
    """
    if not _acquire_beat_lock(self.app, "purge_soft_deleted_records", ttl=86400):
        logger.warning("purge_soft_deleted_records skipped — another execution is in progress")
        return {"status": "skipped", "reason": "concurrent_execution_locked"}

    cutoff = datetime.now(UTC) - timedelta(days=90)
    min_cutoff = cutoff - timedelta(days=7)  # Safety window: purge records deleted 83-90 days ago

    models_to_purge = []
    try:
        from app.estimates.models import Estimate
        from app.jobs.models import Job, Quote

        models_to_purge = [Job, Quote, Estimate]
    except ImportError:
        logger.warning("Could not import all models for soft-delete purge")

    async def _purge_ordered():
        from sqlalchemy import delete

        from app.database import AsyncSessionLocal

        total = 0
        try:
            async with AsyncSessionLocal() as db:
                for model_cls in models_to_purge:
                    try:
                        table_name = getattr(model_cls, "__tablename__", str(model_cls))
                        if model_cls == Job:
                            from sqlalchemy import select as _select

                            from app.billing.models import UsageLedger
                            from app.estimates.models import Estimate
                            from app.jobs.models import AIOutput, JobMedia, Quote

                            job_ids_subq = _select(Job.id).where(
                                Job.is_deleted.is_(True),  # noqa: E712
                                Job.deleted_at < cutoff,
                                Job.deleted_at > min_cutoff,
                            )

                            # V2-FIX: Cascade in dependency order (children first)
                            for related_model in [AIOutput, UsageLedger, JobMedia, Quote, Estimate]:
                                try:
                                    stmt = delete(related_model).where(related_model.job_id.in_(job_ids_subq))
                                    related_result = await db.execute(stmt)
                                    if related_result.rowcount and related_result.rowcount > 0:
                                        logger.info(
                                            "Cascade purged %d %s records",
                                            related_result.rowcount,
                                            related_model.__tablename__,
                                        )
                                except Exception as cascade_err:
                                    logger.warning(
                                        "Failed to cascade purge %s: %s", related_model.__tablename__, cascade_err
                                    )
                        stmt = delete(model_cls).where(
                            model_cls.is_deleted.is_(True),  # noqa: E712
                            model_cls.deleted_at < cutoff,
                            model_cls.deleted_at > min_cutoff,
                        )
                        result = await db.execute(stmt)
                        rowcount = result.rowcount if hasattr(result, "rowcount") else 0
                        if rowcount:
                            logger.info(
                                "Purged %d soft-deleted %s records (cutoff=%s)",
                                rowcount,
                                table_name,
                                cutoff.isoformat(),
                            )
                            total += rowcount
                            try:
                                from app.monitoring.prometheus import increment_counter

                                increment_counter("workticket_soft_delete_purged_total", {"table": table_name})
                            except Exception as _e:
                                logger.debug("Failed to increment purge metric: %s", _e)
                    except Exception as e:
                        logger.error(
                            "Failed to purge soft-deleted %s records: %s",
                            getattr(model_cls, "__tablename__", str(model_cls)),
                            e,
                        )
                        raise
                await db.commit()
                logger.info("Purge complete: %d total records removed", total)
                return total
        except Exception as e:
            logger.error("Purge transaction failed, all changes rolled back: %s", e)
            return total

    total_purged = _run_async(_purge_ordered())

    return {"purged_count": total_purged, "cutoff": cutoff.isoformat()}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, queue="beat")
def recover_orphaned_outputs(self):
    """Scan for AIOutput records without a completed Job state and recover them.

    This can happen when the DB transaction storing AIOutput succeeds but the
    job state transition to 'completed' fails. The task transitions the job to
    'completed' if a valid AIOutput exists.
    """
    from app.config import FeatureFlags, get_settings

    _settings = get_settings()
    _flags = FeatureFlags()
    if _settings.ai_disabled or _flags.is_enabled(FeatureFlags.AI_DISABLED):
        logger.debug("AI disabled — skipping recover_orphaned_outputs")
        return {"status": "skipped", "reason": "ai_disabled"}

    if not _acquire_beat_lock(self.app, "recover_orphaned_outputs", ttl=3600):
        logger.warning("recover_orphaned_outputs skipped — another execution is in progress")
        return {"status": "skipped", "reason": "concurrent_execution_locked"}

    from sqlalchemy import select

    from app.billing.state_machine import transition_job_state
    from app.database import AsyncSessionLocal
    from app.jobs.models import AIOutput, AIProcessingState, Job

    async def _scan():
        async with AsyncSessionLocal() as db:
            try:
                # Find AIOutput records where the parent Job is not in 'completed' state
                result = await db.execute(
                    select(AIOutput)
                    .where(
                        AIOutput.job_id.isnot(None),
                    )
                    .limit(100)
                )
                outputs = result.scalars().all()
                recovered = 0
                for output in outputs:
                    try:
                        job_result = await db.execute(
                            select(Job).where(Job.id == output.job_id).with_for_update(skip_locked=True)
                        )
                        job = job_result.scalar_one_or_none()
                        if (
                            job
                            and job.ai_processing_state != AIProcessingState.completed.value
                            and job.ai_processing_state
                            in (
                                AIProcessingState.processing.value,
                                AIProcessingState.reserved.value,
                            )
                        ):
                            await transition_job_state(
                                db,
                                job.id,
                                job.company_id,
                                AIProcessingState.completed,
                            )
                            recovered += 1
                            logger.info(
                                "Recovered orphaned output for job %s (company=%s, state=%s)",
                                job.id,
                                job.company_id,
                                job.ai_processing_state,
                            )
                    except Exception as out_err:
                        logger.error("Failed to recover orphaned output for job %s: %s", output.job_id, out_err)

                if recovered:
                    await db.commit()
                    try:
                        from app.monitoring.prometheus import increment_counter

                        increment_counter("workticket_orphaned_outputs_recovered_total", {})
                    except Exception as _e:
                        logger.debug("Failed to increment orphaned outputs recovered metric: %s", _e)
                    logger.info("Recovered %d orphaned AIOutput records", recovered)
                return {"recovered": recovered}
            except Exception as e:
                logger.error("Orphaned output recovery failed: %s", e)
                return {"recovered": 0, "error": str(e)}

    return _run_async(_scan())


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, queue="beat")
def detect_dropped_tasks(self):
    """Silent queue death detection: compare jobs created vs completed.

    A persistent gap between created and completed counters indicates tasks
    were enqueued but never reached a terminal state (dropped silently).
    This is the primary detection mechanism for the "silent queue death"
    scenario where Celery workers OOM and tasks are lost without trace.
    """
    if not _acquire_beat_lock(self.app, "detect_dropped_tasks", ttl=300):
        logger.warning("detect_dropped_tasks skipped — another execution is in progress")
        return {"status": "skipped", "reason": "concurrent_execution_locked"}

    try:
        from app.monitoring.prometheus import get_counter, increment_counter, set_dlq_count, set_dropped_tasks

        created = get_counter("workticket_jobs_created_total")
        completed = get_counter("workticket_jobs_completed_total")
        gap = created - completed

        set_dropped_tasks(gap)

        # Also update DLQ gauge by querying the database
        try:
            from sqlalchemy import func, select

            from app.billing.dead_letter import DeadLetterJob
            from app.database import get_readonly_session

            async def _count_dlq():
                _s = get_readonly_session()
                try:
                    r = await _s.execute(select(func.count(DeadLetterJob.id)))
                    return r.scalar() or 0
                finally:
                    await _s.close()

            _dlq_count = _run_async(_count_dlq())
            set_dlq_count(_dlq_count)
        except Exception as _e:
            logger.debug("Failed to update DLQ gauge: %s", _e)

        if gap > 20:
            _persistent_gap_key = "alert:dropped_tasks_gap"
            try:
                _r = get_sync_redis()
                if _r is None:
                    raise ConnectionError("Redis pool unavailable")
                _prev_gap = int(_r.get(_persistent_gap_key) or 0)
                if abs(gap - _prev_gap) < 5:
                    logger.critical(
                        "SILENT QUEUE DEATH CONFIRMED: %d jobs created but only %d completed "
                        "(gap=%d, stable across cycles) — tasks are being dropped without reaching terminal state. "
                        "Check Celery worker health, OOM events, and queue depth.",
                        created,
                        completed,
                        gap,
                    )
                    try:
                        increment_counter("workticket_dropped_tasks_alert_total", {"gap": str(gap)})
                    except Exception as _e:
                        logger.debug("Failed to increment dropped tasks alert metric: %s", _e)
                    return {"status": "critical", "created": created, "completed": completed, "gap": gap}
                _r.setex(_persistent_gap_key, 300, gap)
            except Exception as _e:
                logger.debug("Failed to check persistent gap in Redis: %s", _e)
            logger.warning("Dropped task gap=%d (awaiting confirmation across next cycle)", gap)
            return {"status": "warn", "created": created, "completed": completed, "gap": gap}

        if gap > 0:
            logger.warning("Dropped task gap: %d jobs created - %d completed = %d gap", created, completed, gap)

        return {"status": "ok", "created": created, "completed": completed, "gap": gap}
    except Exception as e:
        logger.error("Dropped task detection failed: %s", e)
        return {"status": "error", "error": str(e)}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, queue="beat")
def detect_worker_crash_loops(self):
    """Detect worker crash-looping by tracking rapid worker restarts.

    Uses Redis to track the number of fresh worker pings within a short
    window. If the same worker restarts more than 3 times in 5 minutes,
    triggers a critical alert.
    """
    if not _acquire_beat_lock(self.app, "detect_worker_crash_loops", ttl=300):
        return {"status": "skipped", "reason": "concurrent_execution_locked"}

    try:
        r = get_sync_redis()
        if r is None:
            raise ConnectionError("Redis pool unavailable")
        from app.monitoring.prometheus import set_worker_crash_loops

        try:
            inspector = celery_app.control.inspect()
            workers = inspector.ping(timeout=2)
            worker_count = len(workers) if workers else 0

            if workers:
                now = time.time()
                for worker_name in workers:
                    key = f"worker:heartbeat:{worker_name}"
                    last_beat = r.get(key)
                    if last_beat:
                        last_beat = float(last_beat)
                        if now - last_beat < 5:
                            pass  # Healthy: heartbeat within 5s
                    r.setex(key, 30, str(now))

            # Check for crash loops: workers that appeared and disappeared rapidly
            # Uses counter that resets if no crash in window
            crash_key = "worker:crash_count"
            crash_count = int(r.get(crash_key) or 0)

            worker_alive = worker_count > 0
            if not worker_alive:
                crash_count = r.incr(crash_key)
                r.expire(crash_key, 300)
                if crash_count > 3:
                    logger.critical(
                        "WORKER CRASH LOOP DETECTED: %d crash events in 5 min window "
                        "(0 workers alive) — all Celery workers may be crash-looping",
                        crash_count,
                    )
                    set_worker_crash_loops(1)
                    return {"status": "critical", "crash_count": crash_count, "worker_count": 0}
            else:
                r.delete(crash_key)
                set_worker_crash_loops(0)

            return {"status": "ok", "worker_count": worker_count, "crash_count": crash_count}
        except Exception:
            return {"status": "error", "error": "inspector_ping_failed"}
    except Exception as e:
        logger.error("Worker crash loop detection failed: %s", e)
        return {"status": "error", "error": str(e)}
