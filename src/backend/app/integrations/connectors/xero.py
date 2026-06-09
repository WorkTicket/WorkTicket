from app.integrations.connectors.base import BaseConnector, ConnectorStatus, ProviderCategory


class XeroConnector(BaseConnector):
    provider = "xero"
    display_name = "Xero"
    category = ProviderCategory.ACCOUNTING
    status = ConnectorStatus.STUB
    description = "Import customers, invoices, and payments from Xero. Coming in Phase 2."
    docs_url = "https://developer.xero.com/documentation/"
    auth_type = "oauth2"
    scopes: list[str] = ("accounting.transactions.read", "accounting.contacts.read")

    async def authenticate(self) -> bool:
        raise NotImplementedError("Xero connector planned for Phase 2.")

    async def fetch_customers(self) -> list:
        raise NotImplementedError("Xero connector planned for Phase 2.")

    async def fetch_jobs(self) -> list:
        raise NotImplementedError("Xero connector planned for Phase 2.")

    async def fetch_work_orders(self) -> list:
        raise NotImplementedError("Xero connector planned for Phase 2.")

    async def fetch_invoices(self) -> list:
        raise NotImplementedError("Xero connector planned for Phase 2.")

    async def fetch_payments(self) -> list:
        raise NotImplementedError("Xero connector planned for Phase 2.")

    async def fetch_employees(self) -> list:
        raise NotImplementedError("Xero connector planned for Phase 2.")

    async def fetch_assets(self) -> list:
        raise NotImplementedError("Xero connector planned for Phase 2.")

    async def fetch_schedule_events(self) -> list:
        raise NotImplementedError("Xero connector planned for Phase 2.")
