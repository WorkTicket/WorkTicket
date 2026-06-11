import logging

import httpx

from app.integrations.canonical import (
    CanonicalCustomer,
    CanonicalEmployee,
    CanonicalInvoice,
    CanonicalJob,
    CanonicalPayment,
)
from app.integrations.connectors.base import (
    BaseConnector,
    ConnectorStatus,
    ProviderCategory,
)
from app.integrations.normalizers.base import BaseNormalizer

logger = logging.getLogger(__name__)

QBO_SANDBOX_BASE = "https://sandbox-quickbooks.api.intuit.com"
QBO_PRODUCTION_BASE = "https://quickbooks.api.intuit.com"
QBO_AUTH_BASE = "https://oauth.platform.intuit.com"
QBO_DISCOVERY_URL = "https://developer.api.intuit.com/.well-known/openid_configuration"


class QuickBooksNormalizer(BaseNormalizer):
    def normalize_customer(self, raw: dict) -> CanonicalCustomer:
        bill_addr = raw.get("BillAddr", {}) or {}
        return CanonicalCustomer(
            external_system="quickbooks",
            external_id=str(raw.get("Id", "")),
            name=raw.get("DisplayName", raw.get("CompanyName", "")),
            email=raw.get("PrimaryEmailAddr", {}).get("Address") if raw.get("PrimaryEmailAddr") else None,
            phone=raw.get("PrimaryPhone", {}).get("FreeFormNumber") if raw.get("PrimaryPhone") else None,
            address_line1=bill_addr.get("Line1"),
            city=bill_addr.get("City"),
            state=bill_addr.get("CountrySubDivisionCode"),
            postal_code=bill_addr.get("PostalCode"),
            country=bill_addr.get("Country"),
            notes=raw.get("Notes"),
            raw_data=raw,
        )

    def normalize_invoice(self, raw: dict) -> CanonicalInvoice:
        customer_ref = raw.get("CustomerRef", {}) or {}
        return CanonicalInvoice(
            external_system="quickbooks",
            external_id=str(raw.get("Id", "")),
            customer_external_id=str(customer_ref.get("value", "")),
            invoice_number=raw.get("DocNumber"),
            status=raw.get("TxnStatus", raw.get("status")),
            subtotal=raw.get("SubTotal"),
            total=raw.get("TotalAmt"),
            currency=raw.get("CurrencyRef", {}).get("value", "USD") if raw.get("CurrencyRef") else "USD",
            due_date=raw.get("DueDate"),
            line_items=raw.get("Line", []),
            notes=raw.get("PrivateNote"),
            raw_data=raw,
        )

    def normalize_payment(self, raw: dict) -> CanonicalPayment:
        customer_ref = raw.get("CustomerRef", {}) or {}
        return CanonicalPayment(
            external_system="quickbooks",
            external_id=str(raw.get("Id", "")),
            customer_external_id=str(customer_ref.get("value", "")),
            amount=raw.get("TotalAmt"),
            currency=raw.get("CurrencyRef", {}).get("value", "USD") if raw.get("CurrencyRef") else "USD",
            payment_method=raw.get("PaymentMethodRef", {}).get("name") if raw.get("PaymentMethodRef") else None,
            payment_date=raw.get("TxnDate"),
            transaction_reference=raw.get("PaymentRefNum"),
            raw_data=raw,
        )

    def normalize_job(self, raw: dict) -> CanonicalJob:
        customer_ref = raw.get("CustomerRef", {}) or {}
        return CanonicalJob(
            external_system="quickbooks",
            external_id=str(raw.get("Id", "")),
            customer_external_id=str(customer_ref.get("value", "")),
            title=raw.get("Name", raw.get("Description", "")),
            description=raw.get("Description"),
            status=raw.get("status", "active"),
            notes=raw.get("Notes"),
            raw_data=raw,
        )

    def normalize_employee(self, raw: dict) -> CanonicalEmployee:
        return CanonicalEmployee(
            external_system="quickbooks",
            external_id=str(raw.get("Id", "")),
            first_name=raw.get("GivenName"),
            last_name=raw.get("FamilyName"),
            email=raw.get("PrimaryEmailAddr", {}).get("Address") if raw.get("PrimaryEmailAddr") else None,
            phone=raw.get("PrimaryPhone", {}).get("FreeFormNumber") if raw.get("PrimaryPhone") else None,
            hire_date=raw.get("HiredDate"),
            is_active=raw.get("Active", True) if isinstance(raw.get("Active"), bool) else True,
            raw_data=raw,
        )


class QuickBooksConnector(BaseConnector):
    provider = "quickbooks"
    display_name = "QuickBooks Online"
    category = ProviderCategory.ACCOUNTING
    status = ConnectorStatus.PRODUCTION
    description = "Import customers, invoices, payments, and employees from QuickBooks Online."
    docs_url = "https://developer.intuit.com/app/developer/qbo/docs/develop"
    auth_type = "oauth2"
    scopes: list[str] = ("com.intuit.quickbooks.accounting",)

    def __init__(self, connection=None):
        super().__init__(connection)
        self._normalizer = QuickBooksNormalizer()
        self._client: httpx.AsyncClient | None = None
        self._realm_id: str | None = None
        self._access_token: str | None = None
        self._sandbox = True
        self.base_url = QBO_SANDBOX_BASE

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
            if self.connection:
                meta = self.connection.metadata_json or {}
                self._realm_id = meta.get("realm_id")
                self._access_token = self.connection.access_token
                self._sandbox = meta.get("sandbox", True)
                self.base_url = QBO_SANDBOX_BASE if self._sandbox else QBO_PRODUCTION_BASE

    async def _get(self, path: str, params: dict | None = None) -> dict:
        await self._ensure_client()
        if not self._realm_id:
            raise ValueError("realm_id not configured. Complete OAuth flow first.")
        url = f"{self.base_url}/v3/company/{self._realm_id}{path}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }
        response = await self._client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    _VALID_ENTITIES = frozenset({
        "Account", "Bill", "BillPayment", "Budget", "Class", "CompanyCurrency",
        "CreditMemo", "Customer", "Department", "Deposit", "Employee",
        "Estimate", "Invoice", "Item", "JournalEntry", "Payment",
        "PaymentMethod", "Purchase", "PurchaseOrder", "RefundReceipt",
        "SalesReceipt", "TaxAgency", "TaxCode", "TaxRate", "Term",
        "TimeActivity", "Transfer", "Vendor", "VendorCredit",
    })

    async def _query_all(self, entity: str, query_filter: str | None = None) -> list[dict]:
        if entity not in self._VALID_ENTITIES:
            raise ValueError(f"Invalid QuickBooks entity: {entity}")
        query = f"SELECT * FROM {entity}"  # nosec B608 -- entity validated against _VALID_ENTITIES whitelist above
        if query_filter:
            query += f" WHERE {query_filter}"
        query += " MAXRESULTS 1000"
        data = await self._get("/query", params={"query": query})
        entities = data.get("QueryResponse", {}).get(entity, [])
        if isinstance(entities, dict):
            entities = [entities]
        return entities  # type: ignore[no-any-return]

    async def authenticate(self) -> bool:
        if self.connection and self.connection.access_token:
            try:
                await self._ensure_client()
                await self._get("/companyinfo/1")
                return True
            except Exception as e:
                logger.warning("QuickBooks authentication failed: %s", e)
                return False
        return False

    async def fetch_customers(self) -> list[CanonicalCustomer]:
        raw_customers = await self._query_all("Customer", "Active = true")
        return [self._normalizer.normalize_customer(c) for c in raw_customers]

    async def fetch_invoices(self) -> list[CanonicalInvoice]:
        raw_invoices = await self._query_all("Invoice")
        return [self._normalizer.normalize_invoice(i) for i in raw_invoices]

    async def fetch_payments(self) -> list[CanonicalPayment]:
        raw_payments = await self._query_all("Payment")
        return [self._normalizer.normalize_payment(p) for p in raw_payments]

    async def fetch_employees(self) -> list[CanonicalEmployee]:
        raw_employees = await self._query_all("Employee", "Active = true")
        return [self._normalizer.normalize_employee(e) for e in raw_employees]

    async def fetch_jobs(self) -> list[CanonicalJob]:
        raw_jobs = await self._query_all("Customer", "Job = true")
        return [self._normalizer.normalize_job(j) for j in raw_jobs]

    async def fetch_work_orders(self) -> list:
        return []

    async def fetch_assets(self) -> list:
        return []

    async def fetch_schedule_events(self) -> list:
        return []

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
