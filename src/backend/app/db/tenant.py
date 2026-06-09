import logging
from typing import Any, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import DeclarativeBase

from app.db.tenant_context import get_current_tenant_id

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=DeclarativeBase)


def tenant_query[T: DeclarativeBase](model: T, company_id: Any = None) -> Select:
    _cid = company_id or get_current_tenant_id()
    if not _cid:
        logger.error(
            "tenant_query called without company_id for model %s — blocking query for safety", model.__tablename__
        )
        from sqlalchemy import false

        return select(model).where(false())
    return select(model).where(model.company_id == _cid)


def tenant_query_by_id[T: DeclarativeBase](model: T, record_id: Any, company_id: Any = None) -> Select:
    _cid = company_id or get_current_tenant_id()
    if not _cid:
        logger.error(
            "tenant_query_by_id called without company_id for model %s — blocking query for safety", model.__tablename__
        )
        from sqlalchemy import false

        return select(model).where(false())
    return select(model).where(model.id == record_id, model.company_id == _cid)
