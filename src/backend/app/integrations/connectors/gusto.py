from app.integrations.connectors.base import BaseConnector, ConnectorStatus, ProviderCategory


class GustoConnector(BaseConnector):
    provider = "gusto"
    display_name = "Gusto"
    category = ProviderCategory.PAYROLL
    status = ConnectorStatus.STUB
    description = "Import employees, roles, and compensation from Gusto. Coming in Phase 2."
    docs_url = "https://docs.gusto.com/"
    auth_type = "oauth2"
    scopes: list[str] = ("read:employees", "read:companies")

    async def authenticate(self) -> bool:
        raise NotImplementedError("Gusto connector planned for Phase 2.")

    async def fetch_customers(self) -> list:
        raise NotImplementedError("Gusto connector planned for Phase 2.")

    async def fetch_jobs(self) -> list:
        raise NotImplementedError("Gusto connector planned for Phase 2.")

    async def fetch_work_orders(self) -> list:
        raise NotImplementedError("Gusto connector planned for Phase 2.")

    async def fetch_invoices(self) -> list:
        raise NotImplementedError("Gusto connector planned for Phase 2.")

    async def fetch_payments(self) -> list:
        raise NotImplementedError("Gusto connector planned for Phase 2.")

    async def fetch_employees(self) -> list:
        raise NotImplementedError("Gusto connector planned for Phase 2.")

    async def fetch_assets(self) -> list:
        raise NotImplementedError("Gusto connector planned for Phase 2.")

    async def fetch_schedule_events(self) -> list:
        raise NotImplementedError("Gusto connector planned for Phase 2.")
