from app.integrations.connectors.base import BaseConnector, ConnectorStatus, ProviderCategory


class AspireConnector(BaseConnector):
    provider = "aspire"
    display_name = "Aspire"
    category = ProviderCategory.FIELD_SERVICE
    status = ConnectorStatus.STUB
    description = "Import customers, jobs, and estimates from Aspire. Coming in Phase 3."
    docs_url = "https://www.youraspire.com/"
    auth_type = "api_key"
    scopes: list[str] = ("read",)

    async def authenticate(self) -> bool:
        raise NotImplementedError("Aspire connector planned for Phase 3.")

    async def fetch_customers(self) -> list:
        raise NotImplementedError("Aspire connector planned for Phase 3.")

    async def fetch_jobs(self) -> list:
        raise NotImplementedError("Aspire connector planned for Phase 3.")

    async def fetch_work_orders(self) -> list:
        raise NotImplementedError("Aspire connector planned for Phase 3.")

    async def fetch_invoices(self) -> list:
        raise NotImplementedError("Aspire connector planned for Phase 3.")

    async def fetch_payments(self) -> list:
        raise NotImplementedError("Aspire connector planned for Phase 3.")

    async def fetch_employees(self) -> list:
        raise NotImplementedError("Aspire connector planned for Phase 3.")

    async def fetch_assets(self) -> list:
        raise NotImplementedError("Aspire connector planned for Phase 3.")

    async def fetch_schedule_events(self) -> list:
        raise NotImplementedError("Aspire connector planned for Phase 3.")
