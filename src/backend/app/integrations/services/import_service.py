import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.connectors.base import ConnectorStatus
from app.integrations.models import (
    ConnectionStatus,
    ImportJob,
    ImportLog,
    ImportResult,
    ImportStatus,
    ImportType,
    IntegrationConnection,
    IntegrationProvider,
    MappingRule,
)
from app.integrations.registry import get_connector

logger = logging.getLogger(__name__)

ENTITY_IMPORT_ORDER = [
    ImportType.CUSTOMERS,
    ImportType.EMPLOYEES,
    ImportType.LOCATIONS,
    ImportType.ASSETS,
    ImportType.JOBS,
    ImportType.WORK_ORDERS,
    ImportType.INVOICES,
    ImportType.PAYMENTS,
    ImportType.SCHEDULE_EVENTS,
]

FETCHER_MAP = {
    ImportType.CUSTOMERS: "fetch_customers",
    ImportType.JOBS: "fetch_jobs",
    ImportType.WORK_ORDERS: "fetch_work_orders",
    ImportType.INVOICES: "fetch_invoices",
    ImportType.PAYMENTS: "fetch_payments",
    ImportType.EMPLOYEES: "fetch_employees",
    ImportType.ASSETS: "fetch_assets",
    ImportType.SCHEDULE_EVENTS: "fetch_schedule_events",
    ImportType.LOCATIONS: "fetch_locations",
}


class ImportService:
    def __init__(self, db: AsyncSession, company_id: UUID):
        self.db = db
        self.company_id = company_id

    async def create_connection(
        self,
        provider: IntegrationProvider,
        tenant: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
        metadata_json: dict | None = None,
    ) -> IntegrationConnection:
        conn = IntegrationConnection(
            company_id=self.company_id,
            provider=provider.value,
            tenant=tenant,
            connection_status=ConnectionStatus.CONNECTED if access_token else ConnectionStatus.PENDING,
            access_token=access_token,
            refresh_token=refresh_token,
            metadata_json=metadata_json or {},
        )
        self.db.add(conn)
        await self.db.flush()
        return conn

    async def get_connection(self, provider: IntegrationProvider, tenant: str = "default") -> IntegrationConnection | None:
        result = await self.db.execute(
            select(IntegrationConnection).where(
                IntegrationConnection.company_id == self.company_id,
                IntegrationConnection.provider == provider.value,
                IntegrationConnection.tenant == tenant,
            )
        )
        return result.scalar_one_or_none()

    async def get_connections(self) -> list[IntegrationConnection]:
        result = await self.db.execute(
            select(IntegrationConnection).where(
                IntegrationConnection.company_id == self.company_id,
            )
        )
        return list(result.scalars().all())

    async def update_connection_status(self, connection_id: UUID, status: ConnectionStatus):
        conn = await self.db.get(IntegrationConnection, connection_id)
        if conn:
            conn.connection_status = status
            conn.updated_at = datetime.now(UTC)
            await self.db.flush()

    async def update_connection_tokens(self, connection_id: UUID, access_token: str, refresh_token: str | None = None, expires_at: datetime | None = None):
        conn = await self.db.get(IntegrationConnection, connection_id)
        if conn:
            conn.access_token = access_token
            if refresh_token:
                conn.refresh_token = refresh_token
            if expires_at:
                conn.token_expires_at = expires_at
            conn.connection_status = ConnectionStatus.CONNECTED
            conn.updated_at = datetime.now(UTC)
            await self.db.flush()

    async def create_import_job(self, provider: IntegrationProvider, import_type: ImportType, connection_id: UUID | None = None) -> ImportJob:
        job = ImportJob(
            company_id=self.company_id,
            connection_id=connection_id,
            provider=provider.value,
            import_type=import_type,
            status=ImportStatus.PENDING,
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get_import_job(self, job_id: UUID) -> ImportJob | None:
        return await self.db.get(ImportJob, job_id)

    async def get_import_jobs(self, limit: int = 50) -> list[ImportJob]:
        result = await self.db.execute(
            select(ImportJob)
            .where(ImportJob.company_id == self.company_id)
            .order_by(ImportJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_import_progress(self, job_id: UUID, status: ImportStatus, progress_pct: float | None = None, imported: int | None = None, skipped: int | None = None, failed: int | None = None, error_message: str | None = None):
        job = await self.db.get(ImportJob, job_id)
        if job:
            job.status = status
            if progress_pct is not None:
                job.progress_pct = progress_pct
            if imported is not None:
                job.imported_count = imported
            if skipped is not None:
                job.skipped_count = skipped
            if failed is not None:
                job.failed_count = failed
            if error_message:
                job.error_message = error_message
            job.updated_at = datetime.now(UTC)
            if status in (ImportStatus.COMPLETED, ImportStatus.PARTIAL, ImportStatus.FAILED):
                job.finished_at = datetime.now(UTC)
            await self.db.flush()

    async def log_import_result(
        self,
        import_job_id: UUID,
        external_system: str,
        external_id: str,
        entity_type: ImportType,
        result: ImportResult,
        internal_id: str | None = None,
        error_message: str | None = None,
        raw_data: dict | None = None,
    ) -> ImportLog:
        log_entry = ImportLog(
            company_id=self.company_id,
            import_job_id=import_job_id,
            external_system=external_system,
            external_id=external_id,
            internal_id=internal_id,
            entity_type=entity_type,
            result=result,
            error_message=error_message,
            raw_data=raw_data,
        )
        self.db.add(log_entry)
        await self.db.flush()
        return log_entry

    async def already_imported(self, external_system: str, external_id: str, entity_type: ImportType) -> bool:
        result = await self.db.execute(
            select(ImportLog).where(
                ImportLog.company_id == self.company_id,
                ImportLog.external_system == external_system,
                ImportLog.external_id == external_id,
                ImportLog.entity_type == entity_type,
                ImportLog.result == ImportResult.SUCCESS,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_mapping_rules(self, provider: str, entity_type: ImportType = None) -> list[MappingRule]:
        query = select(MappingRule).where(
            MappingRule.company_id == self.company_id,
            MappingRule.provider == provider,
        )
        if entity_type:
            query = query.where(MappingRule.entity_type == entity_type)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def save_mapping_rule(self, provider: str, source_field: str, destination_field: str, entity_type: ImportType, transformation_rule: str | None = None) -> MappingRule:
        rule = MappingRule(
            company_id=self.company_id,
            provider=provider,
            source_field=source_field,
            destination_field=destination_field,
            entity_type=entity_type,
            transformation_rule=transformation_rule,
        )
        self.db.add(rule)
        await self.db.flush()
        return rule

    async def delete_mapping_rule(self, rule_id: UUID):
        rule = await self.db.get(MappingRule, rule_id)
        if rule:
            await self.db.delete(rule)
            await self.db.flush()

    async def scan_provider(self, provider: IntegrationProvider, connection_id: UUID | None = None) -> dict:
        connector_cls = get_connector(provider.value)
        if connector_cls.status in (ConnectorStatus.STUB,):
            return {"status": "unavailable", "reason": f"{provider.value} connector is not yet available"}

        connection = None
        if connection_id:
            connection = await self.db.get(IntegrationConnection, connection_id)

        connector_instance = connector_cls(connection=connection)
        try:
            await connector_instance.authenticate()
            counts = await connector_instance.scan()
        finally:
            if hasattr(connector_instance, "close"):
                await connector_instance.close()

        return {
            "status": "ready",
            "provider": provider.value,
            "display_name": connector_cls.display_name,
            "counts": counts,
        }

    async def run_import(
        self,
        provider: IntegrationProvider,
        import_types: list[ImportType],
        connection_id: UUID | None = None,
        dry_run: bool = False,
        batch_size: int = 500,
    ) -> list[ImportJob]:
        connector_cls = get_connector(provider.value)
        if connector_cls.status in (ConnectorStatus.STUB,):
            raise ValueError(f"{provider.value} connector is not yet available")

        connection = None
        if connection_id:
            connection = await self.db.get(IntegrationConnection, connection_id)

        connector_instance = connector_cls(connection=connection)
        jobs = []

        try:
            await connector_instance.authenticate()

            for import_type in import_types:
                job = await self.create_import_job(provider, import_type, connection_id)

                if dry_run:
                    await self.update_import_progress(job.id, ImportStatus.SCANNING, progress_pct=0)

                fetcher_name = FETCHER_MAP.get(import_type)
                fetcher = getattr(connector_instance, fetcher_name, None)

                if fetcher is None:
                    await self.update_import_progress(
                        job.id, ImportStatus.FAILED, error_message=f"No fetcher for {import_type.value}"
                    )
                    jobs.append(job)
                    continue

                try:
                    records = await fetcher()
                    job.total_records = len(records)

                    if dry_run:
                        existing = 0
                        for r in records:
                            ext_id = getattr(r, "external_id", str(getattr(r, "id", "")))
                            if await self.already_imported(provider.value, str(ext_id), import_type):
                                existing += 1
                        await self.update_import_progress(
                            job.id, ImportStatus.COMPLETED, progress_pct=100,
                            imported=0, skipped=0, failed=0,
                            error_message=None,
                        )
                        job.total_records = len(records)
                        jobs.append(job)
                        continue

                    await self.update_import_progress(job.id, ImportStatus.IN_PROGRESS, progress_pct=0)
                    imported = 0
                    skipped = 0
                    failed = 0

                    for batch_start in range(0, len(records), batch_size):
                        batch = records[batch_start:batch_start + batch_size]
                        for i, record in enumerate(batch):
                            record_idx = batch_start + i
                            external_id = getattr(record, "external_id", str(getattr(record, "id", record_idx)))
                            try:
                                if await self.already_imported(provider.value, str(external_id), import_type):
                                    await self.log_import_result(
                                        job.id, provider.value, str(external_id), import_type, ImportResult.DUPLICATE
                                    )
                                    skipped += 1
                                else:
                                    await self.log_import_result(
                                        job.id, provider.value, str(external_id), import_type, ImportResult.SUCCESS,
                                        raw_data=record.model_dump() if hasattr(record, "model_dump") else None,
                                    )
                                    imported += 1
                            except Exception as e:
                                await self.log_import_result(
                                    job.id, provider.value, str(external_id), import_type, ImportResult.FAILED,
                                    error_message=str(e),
                                )
                                failed += 1

                            progress = ((record_idx + 1) / len(records)) * 100 if records else 100
                            await self.update_import_progress(
                                job.id, ImportStatus.IN_PROGRESS, progress_pct=progress,
                                imported=imported, skipped=skipped, failed=failed,
                            )

                        await self.db.flush()

                    final_status = ImportStatus.COMPLETED
                    if failed > 0 and imported > 0:
                        final_status = ImportStatus.PARTIAL
                    elif failed > 0 and imported == 0:
                        final_status = ImportStatus.FAILED

                    await self.update_import_progress(
                        job.id, final_status, progress_pct=100,
                        imported=imported, skipped=skipped, failed=failed,
                    )
                except Exception as e:
                    await self.update_import_progress(
                        job.id, ImportStatus.FAILED, error_message=str(e),
                    )

                jobs.append(job)
        finally:
            if hasattr(connector_instance, "close"):
                await connector_instance.close()

        return jobs

    async def dry_run_scan(
        self,
        provider: IntegrationProvider,
        import_types: list[ImportType],
        connection_id: UUID | None = None,
    ) -> dict:
        connector_cls = get_connector(provider.value)
        if connector_cls.status in (ConnectorStatus.STUB,):
            return {"status": "unavailable", "reason": f"{provider.value} connector is not yet available"}

        connection = None
        if connection_id:
            connection = await self.db.get(IntegrationConnection, connection_id)

        connector_instance = connector_cls(connection=connection)
        try:
            await connector_instance.authenticate()
        except Exception as e:
            return {"status": "error", "reason": str(e)}

        results = {}
        for import_type in import_types:
            fetcher_name = FETCHER_MAP.get(import_type)
            fetcher = getattr(connector_instance, fetcher_name, None)
            if fetcher is None:
                results[import_type.value] = {"total": 0, "new": 0, "duplicates": 0}
                continue

            try:
                records = await fetcher()
                new_count = 0
                dup_count = 0
                for r in records:
                    ext_id = getattr(r, "external_id", str(getattr(r, "id", "")))
                    if await self.already_imported(provider.value, str(ext_id), import_type):
                        dup_count += 1
                    else:
                        new_count += 1
                results[import_type.value] = {
                    "total": len(records),
                    "new": new_count,
                    "duplicates": dup_count,
                }
            except Exception as e:
                results[import_type.value] = {"total": -1, "new": 0, "duplicates": 0, "error": str(e)}

        if hasattr(connector_instance, "close"):
            await connector_instance.close()

        return {
            "status": "ok",
            "provider": provider.value,
            "results": results,
        }

    async def check_connection_health(self, connection_id: UUID) -> dict:
        conn = await self.db.get(IntegrationConnection, connection_id)
        if not conn or conn.company_id != self.company_id:
            raise ValueError("Connection not found")

        try:
            connector_cls = get_connector(conn.provider)
        except ValueError:
            return {"status": "error", "reason": f"Unknown provider: {conn.provider}"}

        connector_instance = connector_cls(connection=conn)
        try:
            health = await connector_instance.check_health()
        finally:
            if hasattr(connector_instance, "close"):
                await connector_instance.close()

        return {
            "connection_id": str(conn.id),
            "provider": conn.provider,
            "tenant": conn.tenant,
            "health": health.value,
            "connection_status": conn.connection_status.value,
            "last_sync_at": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
            "last_error": connector_instance._last_error,
        }

    async def get_import_report(self, job_id: UUID) -> dict:
        job = await self.get_import_job(job_id)
        if not job:
            raise ValueError(f"Import job {job_id} not found")

        result = await self.db.execute(
            select(ImportLog).where(ImportLog.import_job_id == job_id)
        )
        logs = list(result.scalars().all())

        return {
            "job_id": str(job.id),
            "provider": job.provider,
            "import_type": job.import_type.value,
            "status": job.status.value,
            "progress_pct": job.progress_pct,
            "total_records": job.total_records,
            "imported": job.imported_count,
            "skipped": job.skipped_count,
            "failed": job.failed_count,
            "error_message": job.error_message,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "logs": [
                {
                    "external_id": log.external_id,
                    "internal_id": log.internal_id,
                    "entity_type": log.entity_type.value,
                    "result": log.result.value,
                    "error_message": log.error_message,
                }
                for log in logs
            ],
        }

    async def rollback_import(self, job_id: UUID) -> dict:
        job = await self.get_import_job(job_id)
        if not job:
            raise ValueError(f"Import job {job_id} not found")
        if job.rolled_back_at:
            raise ValueError(f"Import job {job_id} already rolled back")

        result = await self.db.execute(
            select(ImportLog).where(
                ImportLog.import_job_id == job_id,
                ImportLog.result == ImportResult.SUCCESS,
            )
        )
        success_logs = list(result.scalars().all())

        rolled_back_count = 0
        for log_entry in success_logs:
            log_entry.result = ImportResult.ROLLED_BACK
            rolled_back_count += 1

        job.rolled_back_at = datetime.now(UTC)
        job.status = ImportStatus.FAILED
        job.imported_count = max(0, job.imported_count - rolled_back_count)
        job.skipped_count += rolled_back_count

        await self.db.flush()
        return {
            "job_id": str(job_id),
            "rolled_back_at": job.rolled_back_at.isoformat(),
            "records_rolled_back": rolled_back_count,
        }

    async def get_migration_metrics(self) -> dict:
        result = await self.db.execute(
            select(ImportJob).where(ImportJob.company_id == self.company_id)
        )
        all_jobs = list(result.scalars().all())

        if not all_jobs:
            return {"total_imports": 0, "success_rate": 0, "avg_duration_seconds": 0}

        completed = [j for j in all_jobs if j.status in (ImportStatus.COMPLETED, ImportStatus.PARTIAL)]
        failed = [j for j in all_jobs if j.status == ImportStatus.FAILED]
        in_progress = [j for j in all_jobs if j.status == ImportStatus.IN_PROGRESS]

        total = len(all_jobs)
        success_rate = (len(completed) / total * 100) if total > 0 else 0

        durations = [
            (j.finished_at - j.started_at).total_seconds()
            for j in completed
            if j.started_at and j.finished_at
        ]

        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_imports": total,
            "completed": len(completed),
            "failed": len(failed),
            "in_progress": len(in_progress),
            "rolled_back_count": len([j for j in all_jobs if j.rolled_back_at]),
            "success_rate_pct": round(success_rate, 1),
            "avg_duration_seconds": round(avg_duration, 1),
            "total_imported": sum(j.imported_count for j in all_jobs),
            "total_skipped": sum(j.skipped_count for j in all_jobs),
            "total_failed_records": sum(j.failed_count for j in all_jobs),
        }
