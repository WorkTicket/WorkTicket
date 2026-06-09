import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authorize import require_admin, require_staff
from app.database import get_db
from app.db.tenant_context import get_current_tenant_id
from app.integrations.connectors.base import ConnectorStatus
from app.integrations.feature_flags import integration_flags
from app.integrations.models import ImportJob, ImportType, IntegrationProvider
from app.integrations.registry import get_available_providers, get_connector, get_providers_by_category
from app.integrations.services.csv_importer import CSVImportEngine
from app.integrations.services.import_service import ImportService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations", "staff"])

csv_engine = CSVImportEngine()


def _check_feature_flag(provider: str):
    flag = integration_flags.get_flag(provider)
    if flag.value == "disabled":
        raise HTTPException(status_code=403, detail=f"Integration {provider} is currently disabled")
    connector_cls = get_connector(provider)
    if connector_cls.status in (ConnectorStatus.STUB,):
        raise HTTPException(status_code=400, detail=f"{provider} connector is not yet available")


def _resolve_provider(provider: str) -> IntegrationProvider:
    try:
        return IntegrationProvider(provider)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}") from err


@router.get("/providers")
async def list_providers(
    category: str | None = Query(None, description="Filter by category"),
    status: str | None = Query(None, description="Filter by status (production, beta, stub)"),
    _user: dict = Depends(require_staff),
):
    if category and status:
        providers = [
            p for p in get_available_providers()
            if p.get("category") == category and p.get("status") == status
        ]
    elif category:
        from app.integrations.connectors.base import ProviderCategory
        try:
            cat = ProviderCategory(category)
            providers = get_providers_by_category(cat)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}") from err
    elif status:
        try:
            stat = ConnectorStatus(status)
            from app.integrations.registry import get_providers_by_status
            providers = get_providers_by_status(stat)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from err
    else:
        providers = get_available_providers()

    return {"success": True, "data": providers}


@router.get("/providers/{provider}")
async def get_provider_details(
    provider: str,
    _user: dict = Depends(require_staff),
):
    try:
        connector_cls = get_connector(provider)
        return {"success": True, "data": connector_cls().to_dict()}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}") from err


@router.get("/connections")
async def list_connections(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    company_id = get_current_tenant_id()
    service = ImportService(db, company_id)
    connections = await service.get_connections()
    return {
        "success": True,
        "data": [
            {
                "id": str(c.id),
                "provider": c.provider,
                "tenant": c.tenant,
                "status": c.connection_status.value,
                "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in connections
        ],
    }


@router.post("/connections")
async def create_connection(
    provider: str = Form(...),
    tenant: str = Form(default="default"),
    access_token: str | None = Form(default=None),
    refresh_token: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    company_id = get_current_tenant_id()
    provider_enum = _resolve_provider(provider)
    _check_feature_flag(provider)

    service = ImportService(db, company_id)
    existing = await service.get_connection(provider_enum, tenant)
    if existing:
        await service.update_connection_tokens(existing.id, access_token, refresh_token)
        return {"success": True, "data": {"id": str(existing.id), "provider": provider, "tenant": tenant, "status": "connected"}}

    conn = await service.create_connection(provider_enum, tenant, access_token, refresh_token)
    await db.commit()
    return {"success": True, "data": {"id": str(conn.id), "provider": provider, "tenant": tenant, "status": conn.connection_status.value}}


@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    from uuid import UUID

    from app.integrations.models import IntegrationConnection

    company_id = get_current_tenant_id()
    conn = await db.get(IntegrationConnection, UUID(connection_id))
    if not conn or conn.company_id != company_id:
        raise HTTPException(status_code=404, detail="Connection not found")

    await db.delete(conn)
    await db.commit()
    return {"success": True, "message": "Connection deleted"}


@router.post("/{provider}/scan")
async def scan_provider(
    provider: str,
    connection_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    company_id = get_current_tenant_id()
    provider_enum = _resolve_provider(provider)
    _check_feature_flag(provider)

    from uuid import UUID as _UUID

    conn_id = _UUID(connection_id) if connection_id else None
    service = ImportService(db, company_id)
    result = await service.scan_provider(provider_enum, conn_id)
    return {"success": True, "data": result}


@router.post("/{provider}/dry-run")
async def dry_run_import(
    provider: str,
    import_types: list[str] = Form(...),
    connection_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    company_id = get_current_tenant_id()
    provider_enum = _resolve_provider(provider)
    _check_feature_flag(provider)

    types = []
    for it in import_types:
        try:
            types.append(ImportType(it))
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Unknown import type: {it}") from err

    from uuid import UUID as _UUID

    conn_id = _UUID(connection_id) if connection_id else None
    service = ImportService(db, company_id)
    result = await service.dry_run_scan(provider_enum, types, conn_id)
    return {"success": True, "data": result}


@router.get("/connections/{connection_id}/health")
async def connection_health(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    from uuid import UUID as _UUID

    company_id = get_current_tenant_id()
    service = ImportService(db, company_id)
    result = await service.check_connection_health(_UUID(connection_id))
    return {"success": True, "data": result}


@router.post("/{provider}/import")
async def start_import(
    provider: str,
    background_tasks: BackgroundTasks,
    import_types: list[str] = Form(...),
    connection_id: str | None = Form(default=None),
    dry_run: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    company_id = get_current_tenant_id()
    provider_enum = _resolve_provider(provider)
    _check_feature_flag(provider)

    types = []
    for it in import_types:
        try:
            types.append(ImportType(it))
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Unknown import type: {it}") from err

    from uuid import UUID as _UUID

    conn_id = _UUID(connection_id) if connection_id else None

    async def _run_import():
        async with db.begin():
            svc = ImportService(db, company_id)
            await svc.run_import(provider_enum, types, conn_id, dry_run=dry_run)

    background_tasks.add_task(_run_import)

    return {"success": True, "message": f"Import started for {provider}", "import_types": import_types, "dry_run": dry_run}


@router.get("/imports")
async def list_imports(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    company_id = get_current_tenant_id()
    service = ImportService(db, company_id)
    jobs = await service.get_import_jobs(limit=limit)
    return {
        "success": True,
        "data": [
            {
                "id": str(j.id),
                "provider": j.provider,
                "import_type": j.import_type.value,
                "status": j.status.value,
                "progress_pct": j.progress_pct,
                "total_records": j.total_records,
                "imported": j.imported_count,
                "skipped": j.skipped_count,
                "failed": j.failed_count,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in jobs
        ],
    }


@router.get("/imports/{import_id}")
async def get_import_details(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    from uuid import UUID as _UUID

    company_id = get_current_tenant_id()
    service = ImportService(db, company_id)
    report = await service.get_import_report(_UUID(import_id))
    return {"success": True, "data": report}


@router.post("/csv/preview")
async def csv_preview(
    file: UploadFile = File(...),
    import_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    try:
        it = ImportType(import_type)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Unknown import type: {import_type}") from err

    content = await file.read()
    preview = csv_engine.preview(content, it)
    return {"success": True, "data": preview}


@router.post("/csv/import")
async def csv_import(
    file: UploadFile = File(...),
    import_type: str = Form(...),
    column_mapping: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    try:
        it = ImportType(import_type)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Unknown import type: {import_type}") from err

    import json as _json

    mapping = None
    if column_mapping:
        try:
            mapping = _json.loads(column_mapping)
        except _json.JSONDecodeError as err:
            raise HTTPException(status_code=400, detail="Invalid column_mapping JSON") from err

    content = await file.read()
    records = csv_engine.parse(content, it, column_mapping=mapping)

    return {
        "success": True,
        "data": {
            "import_type": import_type,
            "records_parsed": len(records),
            "records": [r.model_dump() for r in records[:100]],
        },
    }


@router.get("/mapping-rules/{provider}")
async def get_mapping_rules(
    provider: str,
    entity_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    company_id = get_current_tenant_id()
    service = ImportService(db, company_id)
    et = ImportType(entity_type) if entity_type else None
    rules = await service.get_mapping_rules(provider, et)
    return {
        "success": True,
        "data": [
            {
                "id": str(r.id),
                "provider": r.provider,
                "source_field": r.source_field,
                "destination_field": r.destination_field,
                "entity_type": r.entity_type.value,
                "transformation_rule": r.transformation_rule,
            }
            for r in rules
        ],
    }


@router.post("/mapping-rules/{provider}")
async def create_mapping_rule(
    provider: str,
    source_field: str = Form(...),
    destination_field: str = Form(...),
    entity_type: str = Form(...),
    transformation_rule: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    company_id = get_current_tenant_id()
    try:
        et = ImportType(entity_type)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type}") from err

    service = ImportService(db, company_id)
    rule = await service.save_mapping_rule(provider, source_field, destination_field, et, transformation_rule)
    await db.commit()
    return {"success": True, "data": {"id": str(rule.id)}}


@router.delete("/mapping-rules/{rule_id}")
async def delete_mapping_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    from uuid import UUID as _UUID

    company_id = get_current_tenant_id()
    service = ImportService(db, company_id)
    await service.delete_mapping_rule(_UUID(rule_id))
    await db.commit()
    return {"success": True, "message": "Mapping rule deleted"}


# ============================================================================
# Rollback & Recovery
# ============================================================================

@router.post("/imports/{import_id}/rollback")
async def rollback_import(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    from uuid import UUID as _UUID

    company_id = get_current_tenant_id()
    service = ImportService(db, company_id)
    try:
        result = await service.rollback_import(_UUID(import_id))
        await db.commit()
        return {"success": True, "data": result}
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


# ============================================================================
# Migration Metrics & Admin Console
# ============================================================================

@router.get("/migration-metrics")
async def get_migration_metrics(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_staff),
):
    company_id = get_current_tenant_id()
    service = ImportService(db, company_id)
    metrics = await service.get_migration_metrics()
    return {"success": True, "data": metrics}


@router.get("/admin/migrations/overview")
async def admin_migration_overview(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_admin),
):
    """Admin-only: aggregate migration stats across all tenants."""
    result = await db.execute(
        select(
            func.count(ImportJob.id).label("total_imports"),
            func.count(ImportJob.id).filter(ImportJob.status.in_(["completed", "partial"])).label("completed"),
            func.count(ImportJob.id).filter(ImportJob.status == "failed").label("failed"),
            func.count(ImportJob.id).filter(ImportJob.rolled_back_at.isnot(None)).label("rolled_back"),
            func.count(func.distinct(ImportJob.company_id)).label("active_tenants"),
        )
    )
    row = result.one()
    return {
        "success": True,
        "data": {
            "total_imports": row.total_imports,
            "completed": row.completed,
            "failed": row.failed,
            "rolled_back": row.rolled_back,
            "active_tenants": row.active_tenants,
        },
    }


@router.get("/admin/migrations/failures")
async def admin_migration_failures(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_admin),
):
    """Admin-only: recent failed imports with error details."""
    result = await db.execute(
        select(ImportJob)
        .where(ImportJob.status == "failed")
        .order_by(ImportJob.created_at.desc())
        .limit(limit)
    )
    jobs = list(result.scalars().all())
    return {
        "success": True,
        "data": [
            {
                "id": str(j.id),
                "company_id": str(j.company_id),
                "provider": j.provider,
                "import_type": j.import_type.value,
                "error_message": j.error_message,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in jobs
        ],
    }


@router.get("/admin/migrations/active")
async def admin_migration_active(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_admin),
):
    """Admin-only: currently running imports."""
    result = await db.execute(
        select(ImportJob)
        .where(ImportJob.status == "in_progress")
        .order_by(ImportJob.created_at.desc())
    )
    jobs = list(result.scalars().all())
    return {
        "success": True,
        "data": [
            {
                "id": str(j.id),
                "company_id": str(j.company_id),
                "provider": j.provider,
                "import_type": j.import_type.value,
                "progress_pct": j.progress_pct,
                "started_at": j.started_at.isoformat() if j.started_at else None,
            }
            for j in jobs
        ],
    }
