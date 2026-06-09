from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

import httpx

from app.integrations.canonical import (
    CanonicalAsset,
    CanonicalCustomer,
    CanonicalEmployee,
    CanonicalInvoice,
    CanonicalJob,
    CanonicalLocation,
    CanonicalPayment,
    CanonicalScheduleEvent,
    CanonicalWorkOrder,
)


class ConnectorStatus(StrEnum):
    STUB = "stub"
    BETA = "beta"
    PRODUCTION = "production"
    INTERNAL = "internal"


class ConnectorFeatureFlag(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    BETA = "beta"
    INTERNAL = "internal"


class ProviderCategory(StrEnum):
    ACCOUNTING = "accounting"
    FIELD_SERVICE = "field_service"
    LANDSCAPING = "landscaping"
    PAYMENTS = "payments"
    CRM = "crm"
    PAYROLL = "payroll"
    SCHEDULING = "scheduling"
    INVENTORY = "inventory"
    ROUTING = "routing"
    COMMUNICATION = "communication"


class ConnectionHealth(StrEnum):
    HEALTHY = "healthy"
    TOKEN_EXPIRING = "token_expiring"
    DISCONNECTED = "disconnected"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    UNKNOWN = "unknown"


class RateLimitConfig:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        respect_retry_after: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.respect_retry_after = respect_retry_after


class BaseConnector(ABC):
    provider: str
    display_name: str
    category: ProviderCategory
    status: ConnectorStatus = ConnectorStatus.STUB
    feature_flag: ConnectorFeatureFlag = ConnectorFeatureFlag.DISABLED
    description: str = ""
    icon_url: str | None = None
    docs_url: str | None = None
    auth_type: str = "oauth2"
    scopes: list[str] = ()
    rate_limit_config: RateLimitConfig = RateLimitConfig()
    health: ConnectionHealth = ConnectionHealth.UNKNOWN

    def __init__(self, connection: Any | None = None):
        self.connection = connection
        self._last_error: str | None = None

    @abstractmethod
    async def authenticate(self) -> bool:
        ...

    @abstractmethod
    async def fetch_customers(self) -> list[CanonicalCustomer]:
        ...

    @abstractmethod
    async def fetch_jobs(self) -> list[CanonicalJob]:
        ...

    @abstractmethod
    async def fetch_work_orders(self) -> list[CanonicalWorkOrder]:
        ...

    @abstractmethod
    async def fetch_invoices(self) -> list[CanonicalInvoice]:
        ...

    @abstractmethod
    async def fetch_payments(self) -> list[CanonicalPayment]:
        ...

    @abstractmethod
    async def fetch_employees(self) -> list[CanonicalEmployee]:
        ...

    @abstractmethod
    async def fetch_assets(self) -> list[CanonicalAsset]:
        ...

    @abstractmethod
    async def fetch_schedule_events(self) -> list[CanonicalScheduleEvent]:
        ...

    async def fetch_locations(self) -> list[CanonicalLocation]:
        return []

    async def scan(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        fetchers = {
            "customers": self.fetch_customers,
            "jobs": self.fetch_jobs,
            "work_orders": self.fetch_work_orders,
            "invoices": self.fetch_invoices,
            "payments": self.fetch_payments,
            "employees": self.fetch_employees,
            "assets": self.fetch_assets,
            "schedule_events": self.fetch_schedule_events,
        }
        for entity_type, fetcher in fetchers.items():
            try:
                records = await fetcher()
                counts[entity_type] = len(records)
            except NotImplementedError:
                counts[entity_type] = 0
            except Exception:
                counts[entity_type] = -1
        return counts

    async def sync_all(self) -> dict[str, list]:
        return {
            "customers": await self.fetch_customers(),
            "jobs": await self.fetch_jobs(),
            "work_orders": await self.fetch_work_orders(),
            "invoices": await self.fetch_invoices(),
            "payments": await self.fetch_payments(),
            "employees": await self.fetch_employees(),
            "assets": await self.fetch_assets(),
            "schedule_events": await self.fetch_schedule_events(),
        }

    async def check_health(self) -> ConnectionHealth:
        try:
            authed = await self.authenticate()
            if not authed:
                self.health = ConnectionHealth.DISCONNECTED
                return self.health
            self.health = ConnectionHealth.HEALTHY
            if self.connection and self.connection.token_expires_at:
                from datetime import UTC, datetime
                days_left = (self.connection.token_expires_at - datetime.now(UTC)).days
                if days_left < 7:
                    self.health = ConnectionHealth.TOKEN_EXPIRING
            return self.health
        except Exception as e:
            self._last_error = str(e)
            self.health = ConnectionHealth.ERROR
            return self.health

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "display_name": self.display_name,
            "category": self.category.value,
            "status": self.status.value,
            "feature_flag": self.feature_flag.value,
            "description": self.description,
            "icon_url": self.icon_url,
            "docs_url": self.docs_url,
            "auth_type": self.auth_type,
            "scopes": list(self.scopes),
            "health": self.health.value,
        }

    async def _retry_request(self, request_coro, method_name: str = "request"):
        config = self.rate_limit_config
        last_exc = None
        for attempt in range(config.max_retries + 1):
            try:
                return await request_coro
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and config.respect_retry_after:
                    retry_after = e.response.headers.get("Retry-After", str(config.base_delay))
                    try:
                        delay = min(float(retry_after), config.max_delay)
                    except ValueError:
                        delay = config.base_delay
                    if attempt < config.max_retries:
                        import asyncio
                        await asyncio.sleep(delay)
                        last_exc = e
                        continue
                self.health = ConnectionHealth.RATE_LIMITED
                raise
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
                if attempt < config.max_retries:
                    import asyncio
                    delay = min(config.base_delay * (2**attempt), config.max_delay)
                    await asyncio.sleep(delay)
                    last_exc = e
                    continue
                self.health = ConnectionHealth.ERROR
                self._last_error = str(e)
                raise
        if last_exc:
            raise last_exc
