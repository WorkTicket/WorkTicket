from contextvars import ContextVar
from uuid import UUID

current_tenant_id: ContextVar[UUID | None] = ContextVar("current_tenant_id", default=None)
current_tenant_set: ContextVar[bool] = ContextVar("current_tenant_set", default=False)


def get_current_tenant_id() -> UUID | None:
    return current_tenant_id.get()


def set_current_tenant_id(tenant_id: UUID | None) -> None:
    current_tenant_id.set(tenant_id)
    current_tenant_set.set(True)


def clear_current_tenant_id() -> None:
    current_tenant_id.set(None)
    current_tenant_set.set(False)


def is_tenant_set() -> bool:
    return current_tenant_set.get()
