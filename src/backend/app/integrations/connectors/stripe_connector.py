import logging
from datetime import datetime

import stripe

from app.integrations.canonical import (
    CanonicalCustomer,
    CanonicalInvoice,
    CanonicalPayment,
)
from app.integrations.connectors.base import (
    BaseConnector,
    ConnectorStatus,
    ProviderCategory,
)
from app.integrations.normalizers.base import BaseNormalizer

logger = logging.getLogger(__name__)


class StripeNormalizer(BaseNormalizer):
    def normalize_customer(self, raw: dict) -> CanonicalCustomer:
        return CanonicalCustomer(
            external_system="stripe",
            external_id=str(raw.get("id", "")),
            name=raw.get("name", raw.get("description", "")),
            email=raw.get("email"),
            phone=raw.get("phone"),
            address_line1=raw.get("address", {}).get("line1") if isinstance(raw.get("address"), dict) else raw.get("address"),
            city=raw.get("address", {}).get("city") if isinstance(raw.get("address"), dict) else None,
            state=raw.get("address", {}).get("state") if isinstance(raw.get("address"), dict) else None,
            postal_code=raw.get("address", {}).get("postal_code") if isinstance(raw.get("address"), dict) else None,
            country=raw.get("address", {}).get("country") if isinstance(raw.get("address"), dict) else "US",
            notes=raw.get("description"),
            raw_data=raw,
        )

    def normalize_invoice(self, raw: dict) -> CanonicalInvoice:
        return CanonicalInvoice(
            external_system="stripe",
            external_id=str(raw.get("id", "")),
            customer_external_id=str(raw.get("customer")),
            invoice_number=raw.get("number", ""),
            status=self._map_invoice_status(raw.get("status", "")),
            subtotal=self._to_cents(raw.get("subtotal")),
            tax=self._to_cents(raw.get("tax")),
            total=self._to_cents(raw.get("total")),
            currency=raw.get("currency", "usd").upper(),
            issued_date=datetime.utcfromtimestamp(raw.get("created", 0)) if raw.get("created") else None,
            due_date=datetime.utcfromtimestamp(raw.get("due_date")) if raw.get("due_date") else None,
            paid_date=datetime.utcfromtimestamp(raw.get("status_transitions", {}).get("paid_at", 0)) if raw.get("status_transitions", {}).get("paid_at") else None,
            line_items=self._extract_line_items(raw),
            raw_data=raw,
        )

    def normalize_payment(self, raw: dict) -> CanonicalPayment:
        invoice_id = raw.get("invoice")
        customer_id = raw.get("customer")
        raw.get("billing_details", {}) or {}
        return CanonicalPayment(
            external_system="stripe",
            external_id=str(raw.get("id", "")),
            customer_external_id=str(customer_id) if customer_id else None,
            invoice_external_id=str(invoice_id) if invoice_id else None,
            amount=self._to_cents(raw.get("amount")),
            currency=raw.get("currency", "usd").upper(),
            payment_method=raw.get("payment_method_details", {}).get("type") if raw.get("payment_method_details") else None,
            status=raw.get("status", ""),
            payment_date=datetime.utcfromtimestamp(raw.get("created", 0)) if raw.get("created") else None,
            transaction_reference=raw.get("id"),
            raw_data=raw,
        )

    @staticmethod
    def _to_cents(amount):
        if amount is None:
            return None
        return amount / 100

    @staticmethod
    def _map_invoice_status(status: str) -> str:
        status_map = {
            "draft": "draft",
            "open": "sent",
            "paid": "paid",
            "uncollectible": "bad_debt",
            "void": "void",
        }
        return status_map.get(status, status)

    def _extract_line_items(self, raw: dict) -> list[dict]:
        lines = raw.get("lines", {}).get("data", [])
        result = []
        for item in lines:
            price = item.get("price", {}) or {}
            result.append({
                "name": item.get("description", price.get("nickname", "")),
                "description": item.get("description", ""),
                "quantity": item.get("quantity", 1),
                "unit_price": self._to_cents(price.get("unit_amount", 0)),
                "total": self._to_cents(item.get("amount", 0)),
                "source_id": str(item.get("id", "")),
            })
        return result


class StripeConnector(BaseConnector):
    provider = "stripe"
    display_name = "Stripe"
    category = ProviderCategory.PAYMENTS
    status = ConnectorStatus.PRODUCTION
    description = "Import customers, invoices, and payments from Stripe."
    docs_url = "https://stripe.com/docs/api"
    auth_type = "api_key"
    scopes: list[str] = ("read",)

    def __init__(self, connection=None):
        super().__init__(connection)
        self._normalizer = StripeNormalizer()
        self._stripe_api_key: str | None = None

    async def _ensure_stripe(self):
        if self._stripe_api_key is None:
            if self.connection and self.connection.access_token:
                self._stripe_api_key = self.connection.access_token
            else:
                self._stripe_api_key = ""

    async def authenticate(self) -> bool:
        if self.connection and self.connection.access_token:
            try:
                self._stripe_api_key = self.connection.access_token
                return True
            except Exception as e:
                logger.warning("Stripe authentication failed: %s", e)
                return False
        return False

    async def fetch_customers(self) -> list[CanonicalCustomer]:
        await self._ensure_stripe()
        customers: list[CanonicalCustomer] = []
        try:
            customers = [
                self._normalizer.normalize_customer(c)
                for c in stripe.Customer.list(limit=100, api_key=self._stripe_api_key).auto_paging_iter()
            ]
        except Exception as e:
            logger.error("Failed to fetch Stripe customers: %s", e)
        return customers

    async def fetch_jobs(self) -> list:
        return []

    async def fetch_work_orders(self) -> list:
        return []

    async def fetch_invoices(self) -> list[CanonicalInvoice]:
        await self._ensure_stripe()
        invoices: list[CanonicalInvoice] = []
        try:
            invoices = [
                self._normalizer.normalize_invoice(inv)
                for inv in stripe.Invoice.list(limit=100, api_key=self._stripe_api_key).auto_paging_iter()
            ]
        except Exception as e:
            logger.error("Failed to fetch Stripe invoices: %s", e)
        return invoices

    async def fetch_payments(self) -> list[CanonicalPayment]:
        await self._ensure_stripe()
        payments: list[CanonicalPayment] = []
        try:
            payments = [
                self._normalizer.normalize_payment(pi)
                for pi in stripe.PaymentIntent.list(limit=100, api_key=self._stripe_api_key).auto_paging_iter()
            ]
        except Exception as e:
            logger.error("Failed to fetch Stripe payment intents: %s", e)
        return payments

    async def fetch_employees(self) -> list:
        return []

    async def fetch_assets(self) -> list:
        return []

    async def fetch_schedule_events(self) -> list:
        return []
