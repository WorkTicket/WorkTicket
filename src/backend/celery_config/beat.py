import logging
import os
import threading

logger = logging.getLogger(__name__)

# Shared beat lock constants
_beat_local_locks: dict = {}
_beat_local_lock_obj = threading.Lock()

# Task routes dict with full dotted paths
task_routes = {
    "tasks.ai_tasks.process_ai_text": {"queue": "ai_text"},
    "tasks.ai_tasks.process_ai_audio": {"queue": "ai_audio"},
    "tasks.ai_tasks.process_ai_image": {"queue": "ai_image"},
    "tasks.job_tasks.process_job_task": {"queue": "default"},
    "tasks.maintenance.cleanup_stale_jobs": {"queue": "beat"},
    "tasks.billing_tasks.refresh_stripe_ips_task": {"queue": "beat"},
    "app.billing.tasks.retry_expired_dead_letter_jobs": {"queue": "beat"},
    "app.billing.tasks.retry_dead_letter_job": {"queue": "beat"},
    "tasks.billing_tasks.reset_billing_quotas": {"queue": "beat"},
    "tasks.billing_tasks.collect_billing_debt": {"queue": "beat"},
    "tasks.billing_tasks.decay_risk_scores_task": {"queue": "beat"},
    "tasks.job_tasks.scan_for_stalled_ai_jobs": {"queue": "beat"},
    "tasks.maintenance.purge_soft_deleted_records": {"queue": "beat"},
    "tasks.maintenance.recover_orphaned_outputs": {"queue": "beat"},
    "app.billing.tasks.replay_dlq_fallback": {"queue": "beat"},
    "app.billing.tasks.merge_dlq_fallback_files": {"queue": "beat"},
    "tasks.billing_tasks.cleanup_dlq_fallback_files": {"queue": "beat"},
    "tasks.billing_tasks.purge_expired_dlq_entries": {"queue": "beat"},
    "tasks.maintenance.cleanup_stale_reservations_task": {"queue": "beat"},
    "tasks.maintenance.alert_stuck_jobs": {"queue": "beat"},
    "tasks.maintenance.cleanup_old_estimates": {"queue": "beat"},
    "tasks.billing_tasks.send_email_task": {"queue": "default"},
    "tasks.maintenance.detect_dropped_tasks": {"queue": "beat"},
    "tasks.maintenance.detect_worker_crash_loops": {"queue": "beat"},
}

beat_schedule = {
    "cleanup-stale-jobs-every-2-min": {
        "task": "tasks.maintenance.cleanup_stale_jobs",
        "schedule": 120.0,
        "options": {"expires": 60.0},
    },
    "refresh-stripe-ips-every-30-minutes": {
        "task": "tasks.billing_tasks.refresh_stripe_ips_task",
        "schedule": 1800.0,
        "options": {"expires": 600.0},
    },
    "reset-billing-quotas-every-5-min": {
        "task": "tasks.billing_tasks.reset_billing_quotas",
        "schedule": 300.0,
        "options": {"expires": 120.0},
    },
    "decay-risk-scores-every-30-min": {
        "task": "tasks.billing_tasks.decay_risk_scores_task",
        "schedule": 1800.0,
        "options": {"expires": 600.0},
    },
    "purge-expired-dlq-entries-daily": {
        "task": "tasks.billing_tasks.purge_expired_dlq_entries",
        "schedule": 86400.0,
        "options": {"expires": 7200.0},
    },
    "purge-old-soft-deleted-records-daily": {
        "task": "tasks.maintenance.purge_soft_deleted_records",
        "schedule": 86400.0,
        "options": {"expires": 7200.0},
    },
    "retry-expired-dead-letter-jobs-every-5-min": {
        "task": "app.billing.tasks.retry_expired_dead_letter_jobs",
        "schedule": 300.0,
        "options": {"expires": 120.0},
    },
    "replay-dlq-fallback-every-5-min": {
        "task": "app.billing.tasks.replay_dlq_fallback",
        "schedule": 300.0,
        "options": {"expires": 120.0},
    },
    "merge-dlq-fallback-files-every-2-min": {
        "task": "app.billing.tasks.merge_dlq_fallback_files",
        "schedule": 120.0,
        "options": {"expires": 60.0},
    },
    "cleanup-dlq-fallback-files-every-5-min": {
        "task": "tasks.billing_tasks.cleanup_dlq_fallback_files",
        "schedule": 300.0,
        "options": {"expires": 120.0},
    },
    "detect-dropped-tasks-every-2-min": {
        "task": "tasks.maintenance.detect_dropped_tasks",
        "schedule": 120.0,
        "options": {"expires": 60.0},
    },
    "detect-worker-crash-loops-every-2-min": {
        "task": "tasks.maintenance.detect_worker_crash_loops",
        "schedule": 120.0,
        "options": {"expires": 60.0},
    },
    "cleanup-stale-reservations-every-5-min": {
        "task": "tasks.maintenance.cleanup_stale_reservations_task",
        "schedule": 300.0,
        "options": {"expires": 120.0},
    },
    "alert-stuck-jobs-every-5-min": {
        "task": "tasks.maintenance.alert_stuck_jobs",
        "schedule": 300.0,
        "options": {"expires": 120.0},
    },
}

_ai_beat_entries = {
    "scan-for-stalled-ai-jobs": {
        "task": "tasks.job_tasks.scan_for_stalled_ai_jobs",
        "schedule": 300.0,
        "options": {"expires": 120.0},
    },
    "recover-orphaned-outputs-every-6-hours": {
        "task": "tasks.maintenance.recover_orphaned_outputs",
        "schedule": 21600.0,
        "options": {"expires": 3600.0},
    },
    "cleanup-old-estimates-daily": {
        "task": "tasks.maintenance.cleanup_old_estimates",
        "schedule": 86400.0,
        "options": {"expires": 7200.0},
    },
}


def _is_ai_disabled() -> bool:
    from app.config import FeatureFlags, get_settings

    _settings = get_settings()
    if _settings.ai_disabled:
        return True
    _flags = FeatureFlags()
    return _flags.is_enabled(FeatureFlags.AI_DISABLED)


def get_effective_beat_schedule() -> dict:
    schedule = dict(beat_schedule)
    if not _is_ai_disabled():
        schedule.update(_ai_beat_entries)
    return schedule


def _check_version_compatibility():
    """Check that this worker's DEPLOY_ID matches the current deploy stored in Redis."""
    deploy_id = os.getenv("DEPLOY_ID", "")
    if not deploy_id:
        return True
    try:
        from app.sync_redis_pool import get_sync_redis

        r = get_sync_redis()
        if r is None:
            return True
        stored = r.get("deploy:current_id")
        if stored and stored.decode() != deploy_id:
            logger.warning("Beat task skipped — deploy ID mismatch (ours=%s, stored=%s)", deploy_id, stored.decode())
            return False
    except Exception as _e:
        logger.debug("Failed to check deploy version compatibility: %s", _e)
    return True


def _acquire_beat_lock(celery_app_instance, task_name: str, ttl: int = 300) -> bool:
    """Redis-based execution lock for beat tasks to prevent overlapping executions.
    V2-FIX: Falls back to local in-process lock during Redis outage.
    """
    try:
        from app.sync_redis_pool import get_sync_redis

        r = get_sync_redis()
        if r is None:
            raise ConnectionError("Redis pool unavailable")
        locked = r.set(f"beat:lock:{task_name}", "1", nx=True, ex=ttl)
        return bool(locked)
    except Exception:
        logger.warning("Redis unavailable for beat lock %s — using local fallback", task_name)

    # V2-FIX: Local fallback during Redis outage
    with _beat_local_lock_obj:
        if task_name in _beat_local_locks:
            return False
        _beat_local_locks[task_name] = True

    def _clear_local_lock():
        import time as _time

        _time.sleep(ttl)
        with _beat_local_lock_obj:
            _beat_local_locks.pop(task_name, None)

    threading.Thread(target=_clear_local_lock, daemon=True).start()
    logger.warning("Using local beat lock fallback for %s (Redis unavailable)", task_name)
    return True


def _write_dispatch_sentinel(task_id: str) -> None:
    """Write a Redis sentinel key to confirm broker delivery."""
    try:
        from app.sync_redis_pool import get_sync_redis

        _sr = get_sync_redis()
        if _sr is None:
            return
        _sr.setex(f"celery:sentinel:{task_id}", 60, "1")
    except Exception as _e:
        logger.debug("Failed to write dispatch sentinel: %s", _e)
