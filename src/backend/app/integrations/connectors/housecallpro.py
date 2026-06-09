import logging
from datetime import datetime

import httpx

from app.integrations.canonical import (
    CanonicalCustomer,
    CanonicalEmployee,
    CanonicalInvoice,
    CanonicalJob,
    CanonicalPayment,
    CanonicalScheduleEvent,
    CanonicalWorkOrder,
)
from app.integrations.connectors.base import (
    BaseConnector,
    ConnectorStatus,
    ProviderCategory,
)
from app.integrations.normalizers.base import BaseNormalizer

logger = logging.getLogger(__name__)

HCP_API_BASE = "https://api.housecallpro.com"


class HousecallProNormalizer(BaseNormalizer):
    def normalize_customer(self, raw: dict) -> CanonicalCustomer:
        return CanonicalCustomer(
            external_system="housecall_pro",
            external_id=str(raw.get("id", "")),
            name=f"{raw.get('first_name', '')} {raw.get('last_name', '')}".strip(),
            email=raw.get("email"),
            phone=raw.get("phone", raw.get("mobile_number")),
            address_line1=raw.get("address", {}).get("street") if isinstance(raw.get("address"), dict) else raw.get("street"),
            city=raw.get("address", {}).get("city") if isinstance(raw.get("address"), dict) else raw.get("city"),
            state=raw.get("address", {}).get("state") if isinstance(raw.get("address"), dict) else raw.get("state"),
            postal_code=raw.get("address", {}).get("zip") if isinstance(raw.get("address"), dict) else raw.get("zip_code"),
            notes=raw.get("notes"),
            raw_data=raw,
        )

    def normalize_job(self, raw: dict) -> CanonicalJob:
        return CanonicalJob(
            external_system="housecall_pro",
            external_id=str(raw.get("id", "")),
            customer_external_id=str(raw.get("customer_id", "")),
            title=raw.get("description", raw.get("name", raw.get("work_description", ""))),
            description=raw.get("work_description", raw.get("notes", "")),
            status=raw.get("status", raw.get("job_status", "")).lower() if raw.get("status") else None,
            scheduled_start=_parse_dt(raw.get("scheduled_start")),
            scheduled_end=_parse_dt(raw.get("scheduled_end")),
            address_line1=raw.get("address", {}).get("street") if isinstance(raw.get("address"), dict) else raw.get("street"),
            city=raw.get("address", {}).get("city") if isinstance(raw.get("address"), dict) else raw.get("city"),
            state=raw.get("address", {}).get("state") if isinstance(raw.get("address"), dict) else raw.get("state"),
            postal_code=raw.get("address", {}).get("zip") if isinstance(raw.get("address"), dict) else raw.get("zip_code"),
            assigned_employee_external_id=_extract_emp_id(raw),
            notes=raw.get("notes"),
            raw_data=raw,
        )

    def normalize_work_order(self, raw: dict) -> CanonicalWorkOrder:
        return CanonicalWorkOrder(
            external_system="housecall_pro",
            external_id=str(raw.get("id", "")),
            title=raw.get("work_description", raw.get("description", "")),
            description=raw.get("work_description", raw.get("notes", "")),
            status=raw.get("status", "").lower(),
            scheduled_date=_parse_dt(raw.get("scheduled_start", raw.get("scheduled_at"))),
            completed_date=_parse_dt(raw.get("completed_at")),
            assigned_employee_external_id=_extract_emp_id(raw),
            line_items=_extract_items(raw),
            notes=raw.get("notes"),
            raw_data=raw,
        )

    def normalize_invoice(self, raw: dict) -> CanonicalInvoice:
        return CanonicalInvoice(
            external_system="housecall_pro",
            external_id=str(raw.get("id", "")),
            customer_external_id=str(raw.get("customer_id", "")),
            invoice_number=raw.get("invoice_number", raw.get("number", "")),
            status=raw.get("status", "").lower(),
            subtotal=raw.get("subtotal", raw.get("amount", raw.get("sub_total"))),
            tax=raw.get("tax_amount", raw.get("tax")),
            total=raw.get("total", raw.get("total_amount")),
            due_date=_parse_dt(raw.get("due_date")),
            paid_date=_parse_dt(raw.get("paid_at")),
            line_items=_extract_items(raw),
            notes=raw.get("notes"),
            raw_data=raw,
        )

    def normalize_payment(self, raw: dict) -> CanonicalPayment:
        return CanonicalPayment(
            external_system="housecall_pro",
            external_id=str(raw.get("id", "")),
            customer_external_id=str(raw.get("customer_id", "")),
            invoice_external_id=str(raw.get("invoice_id", "")),
            amount=raw.get("amount"),
            payment_method=raw.get("payment_method", raw.get("method")),
            status=raw.get("status", "").lower(),
            payment_date=_parse_dt(raw.get("payment_date", raw.get("paid_at"))),
            transaction_reference=raw.get("transaction_id", raw.get("reference")),
            raw_data=raw,
        )

    def normalize_employee(self, raw: dict) -> CanonicalEmployee:
        return CanonicalEmployee(
            external_system="housecall_pro",
            external_id=str(raw.get("id", "")),
            first_name=raw.get("first_name", ""),
            last_name=raw.get("last_name", ""),
            email=raw.get("email"),
            phone=raw.get("phone", raw.get("mobile_number")),
            role=raw.get("role", raw.get("employee_type")),
            is_active=raw.get("active", raw.get("is_active", True)) if isinstance(raw.get("active", True), bool) else True,
            raw_data=raw,
        )

    def normalize_schedule_event(self, raw: dict) -> CanonicalScheduleEvent:
        return CanonicalScheduleEvent(
            external_system="housecall_pro",
            external_id=str(raw.get("id", "")),
            title=raw.get("title", raw.get("description", "")),
            start_time=_parse_dt(raw.get("scheduled_start", raw.get("start"))),
            end_time=_parse_dt(raw.get("scheduled_end", raw.get("end"))),
            employee_external_id=_extract_emp_id(raw),
            job_external_id=str(raw.get("job_id", raw.get("visit_id", ""))),
            customer_external_id=str(raw.get("customer_id", "")),
            status=raw.get("status", "").lower(),
            raw_data=raw,
        )


def _parse_dt(val) -> datetime | None:
    if not val:
        return None
    try:
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _extract_emp_id(raw: dict) -> str | None:
    emp = raw.get("employee", raw.get("assigned_employee", raw.get("technician", {})))
    if isinstance(emp, dict):
        return str(emp.get("id", emp.get("employee_id", "")))
    if emp:
        return str(emp)
    emps = raw.get("employees", raw.get("assigned_employees", []))
    if emps and isinstance(emps, list):
        first = emps[0]
        if isinstance(first, dict):
            return str(first.get("id", ""))
        return str(first)
    return None


def _extract_items(raw: dict) -> list[dict]:
    items = raw.get("items", raw.get("line_items", raw.get("services", [])))
    return [
        {
            "name": item.get("name", item.get("description", "")),
            "description": item.get("description", ""),
            "quantity": item.get("quantity", 1),
            "unit_price": item.get("unit_price", item.get("price", item.get("rate", 0))),
            "total": item.get("total", item.get("line_total", 0)),
            "source_id": str(item.get("id", "")),
        }
        for item in (items or [])
    ]


class HousecallProConnector(BaseConnector):
    provider = "housecall_pro"
    display_name = "Housecall Pro"
    category = ProviderCategory.FIELD_SERVICE
    status = ConnectorStatus.PRODUCTION
    description = "Import customers, jobs, invoices, payments, employees, and schedules from Housecall Pro."
    docs_url = "https://developer.housecallpro.com/"
    auth_type = "api_key"
    scopes: list[str] = ("read",)

    def __init__(self, connection=None):
        super().__init__(connection)
        self._normalizer = HousecallProNormalizer()
        self._client: httpx.AsyncClient | None = None
        self._api_key: str | None = None

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
            if self.connection:
                self._api_key = self.connection.access_token

    async def _get(self, path: str, params: dict | None = None) -> dict:
        await self._ensure_client()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        response = await self._client.get(f"{HCP_API_BASE}{path}", headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def _get_all(self, path: str) -> list[dict]:
        page = 1
        all_items = []
        while True:
            data = await self._get(path, params={"page": page, "page_size": 100})
            items = data.get("items", data.get("results", data.get("data", [])))
            if not items and isinstance(data, list):
                items = data
            all_items.extend(items if items else [])
            total_pages = data.get("total_pages", data.get("meta", {}).get("total_pages", 1))
            if page >= total_pages or not items:
                break
            page += 1
        return all_items

    async def authenticate(self) -> bool:
        if self.connection and self.connection.access_token:
            try:
                await self._ensure_client()
                await self._get("/company")
                return True
            except Exception as e:
                logger.warning("Housecall Pro authentication failed: %s", e)
                return False
        return False

    async def fetch_customers(self) -> list[CanonicalCustomer]:
        items = await self._get_all("/customers")
        return [self._normalizer.normalize_customer(c) for c in items]

    async def fetch_jobs(self) -> list[CanonicalJob]:
        items = await self._get_all("/jobs")
        return [self._normalizer.normalize_job(j) for j in items]

    async def fetch_work_orders(self) -> list[CanonicalWorkOrder]:
        items = await self._get_all("/work_orders")
        return [self._normalizer.normalize_work_order(w) for w in items]

    async def fetch_invoices(self) -> list[CanonicalInvoice]:
        items = await self._get_all("/invoices")
        return [self._normalizer.normalize_invoice(i) for i in items]

    async def fetch_payments(self) -> list[CanonicalPayment]:
        items = await self._get_all("/payments")
        return [self._normalizer.normalize_payment(p) for p in items]

    async def fetch_employees(self) -> list[CanonicalEmployee]:
        items = await self._get_all("/employees")
        return [self._normalizer.normalize_employee(e) for e in items]

    async def fetch_assets(self) -> list:
        return []

    async def fetch_schedule_events(self) -> list[CanonicalScheduleEvent]:
        items = await self._get_all("/schedule_events")
        return [self._normalizer.normalize_schedule_event(s) for s in items]

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
