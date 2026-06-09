from app.integrations.connectors.base import BaseConnector, ConnectorStatus, ProviderCategory


class ServiceTitanConnector(BaseConnector):
    provider = "servicetitan"
    display_name = "ServiceTitan"
    category = ProviderCategory.FIELD_SERVICE
    status = ConnectorStatus.STUB
    description = "Import customers, jobs, invoices, and payments from ServiceTitan. Coming in Phase 3."
    docs_url = "https://developer.servicetitan.com/"
    auth_type = "oauth2"
    scopes: list[str] = ("read",)

    async def authenticate(self) -> bool:
        raise NotImplementedError("ServiceTitan connector planned for Phase 3.")

    async def fetch_customers(self) -> list:
        raise NotImplementedError("ServiceTitan connector planned for Phase 3.")

    async def fetch_jobs(self) -> list:
        raise NotImplementedError("ServiceTitan connector planned for Phase 3.")

    async def fetch_work_orders(self) -> list:
        raise NotImplementedError("ServiceTitan connector planned for Phase 3.")

    async def fetch_invoices(self) -> list:
        raise NotImplementedError("ServiceTitan connector planned for Phase 3.")

    async def fetch_payments(self) -> list:
        raise NotImplementedError("ServiceTitan connector planned for Phase 3.")

    async def fetch_employees(self) -> list:
        raise NotImplementedError("ServiceTitan connector planned for Phase 3.")

    async def fetch_assets(self) -> list:
        raise NotImplementedError("ServiceTitan connector planned for Phase 3.")

    async def fetch_schedule_events(self) -> list:
        raise NotImplementedError("ServiceTitan connector planned for Phase 3.")
