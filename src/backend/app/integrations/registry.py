from app.integrations.connectors.aspire import AspireConnector
from app.integrations.connectors.base import BaseConnector, ConnectorStatus, ProviderCategory
from app.integrations.connectors.gusto import GustoConnector
from app.integrations.connectors.housecallpro import HousecallProConnector
from app.integrations.connectors.hubspot import HubSpotConnector
from app.integrations.connectors.jobber import JobberConnector
from app.integrations.connectors.lmn import LMNConnector
from app.integrations.connectors.quickbooks import QuickBooksConnector
from app.integrations.connectors.servicetitan import ServiceTitanConnector
from app.integrations.connectors.stripe_connector import StripeConnector
from app.integrations.connectors.xero import XeroConnector

PROVIDERS: dict[str, type[BaseConnector]] = {
    "quickbooks": QuickBooksConnector,
    "jobber": JobberConnector,
    "housecall_pro": HousecallProConnector,
    "stripe": StripeConnector,
    "xero": XeroConnector,
    "lmn": LMNConnector,
    "hubspot": HubSpotConnector,
    "gusto": GustoConnector,
    "servicetitan": ServiceTitanConnector,
    "aspire": AspireConnector,
}


def get_connector(provider: str) -> type[BaseConnector]:
    connector_cls = PROVIDERS.get(provider)
    if connector_cls is None:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}")
    return connector_cls


def get_available_providers() -> list[dict]:
    return [connector_cls().to_dict() for connector_cls in PROVIDERS.values()]


def get_providers_by_category(category: ProviderCategory) -> list[dict]:
    return [c().to_dict() for c in PROVIDERS.values() if c().category == category]


def get_providers_by_status(status: ConnectorStatus) -> list[dict]:
    return [c().to_dict() for c in PROVIDERS.values() if c().status == status]
