from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy import select as sa_select


class SoftDeleteMixin:
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = datetime.now(UTC)

    @classmethod
    def active_select(cls):
        """Return a select() that excludes soft-deleted records."""
        return sa_select(cls).where(cls.is_deleted.is_(False))
