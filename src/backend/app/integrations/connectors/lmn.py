from app.integrations.connectors.base import BaseConnector, ConnectorStatus, ProviderCategory


class LMNConnector(BaseConnector):
    provider = "lmn"
    display_name = "LMN (Landscape Management Network)"
    category = ProviderCategory.LANDSCAPING
    status = ConnectorStatus.STUB
    description = "Import customers, jobs, and schedules from LMN. Coming in Phase 2."
    docs_url = "https://golmn.com/"
    auth_type = "api_key"
    scopes: list[str] = ("read",)

    async def authenticate(self) -> bool:
        raise NotImplementedError("LMN connector planned for Phase 2.")

    async def fetch_customers(self) -> list:
        raise NotImplementedError("LMN connector planned for Phase 2.")

    async def fetch_jobs(self) -> list:
        raise NotImplementedError("LMN connector planned for Phase 2.")

    async def fetch_work_orders(self) -> list:
        raise NotImplementedError("LMN connector planned for Phase 2.")

    async def fetch_invoices(self) -> list:
        raise NotImplementedError("LMN connector planned for Phase 2.")

    async def fetch_payments(self) -> list:
        raise NotImplementedError("LMN connector planned for Phase 2.")

    async def fetch_employees(self) -> list:
        raise NotImplementedError("LMN connector planned for Phase 2.")

    async def fetch_assets(self) -> list:
        raise NotImplementedError("LMN connector planned for Phase 2.")

    async def fetch_schedule_events(self) -> list:
        raise NotImplementedError("LMN connector planned for Phase 2.")
