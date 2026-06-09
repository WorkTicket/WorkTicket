import logging
from typing import Any, TypeVar

from sqlalchemy import Select, select

from app.db.tenant_context import get_current_tenant_id

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TenantScopedQueryMixin:
    @classmethod
    def by_company(cls, company_id: Any = None) -> Select:
        _cid = company_id or get_current_tenant_id()
        if not _cid:
            logger.error(
                "by_company called without company_id for model %s — blocking query for safety", cls.__tablename__
            )
            from sqlalchemy import false

            return select(cls).where(false())
        return select(cls).where(cls.company_id == _cid)

    @classmethod
    def by_id_and_company(cls, record_id: Any, company_id: Any = None) -> Select:
        _cid = company_id or get_current_tenant_id()
        if not _cid:
            logger.error(
                "by_id_and_company called without company_id for model %s — blocking query for safety",
                cls.__tablename__,
            )
            from sqlalchemy import false

            return select(cls).where(false())
        return select(cls).where(cls.id == record_id, cls.company_id == _cid)
