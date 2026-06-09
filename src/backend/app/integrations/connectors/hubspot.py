from app.integrations.connectors.base import BaseConnector, ConnectorStatus, ProviderCategory


class HubSpotConnector(BaseConnector):
    provider = "hubspot"
    display_name = "HubSpot"
    category = ProviderCategory.CRM
    status = ConnectorStatus.STUB
    description = "Import contacts, deals, and companies from HubSpot. Coming in Phase 2."
    docs_url = "https://developers.hubspot.com/docs/api"
    auth_type = "oauth2"
    scopes: list[str] = ("crm.objects.contacts.read", "crm.objects.deals.read", "crm.objects.companies.read")

    async def authenticate(self) -> bool:
        raise NotImplementedError("HubSpot connector planned for Phase 2.")

    async def fetch_customers(self) -> list:
        raise NotImplementedError("HubSpot connector planned for Phase 2.")

    async def fetch_jobs(self) -> list:
        raise NotImplementedError("HubSpot connector planned for Phase 2.")

    async def fetch_work_orders(self) -> list:
        raise NotImplementedError("HubSpot connector planned for Phase 2.")

    async def fetch_invoices(self) -> list:
        raise NotImplementedError("HubSpot connector planned for Phase 2.")

    async def fetch_payments(self) -> list:
        raise NotImplementedError("HubSpot connector planned for Phase 2.")

    async def fetch_employees(self) -> list:
        raise NotImplementedError("HubSpot connector planned for Phase 2.")

    async def fetch_assets(self) -> list:
        raise NotImplementedError("HubSpot connector planned for Phase 2.")

    async def fetch_schedule_events(self) -> list:
        raise NotImplementedError("HubSpot connector planned for Phase 2.")
