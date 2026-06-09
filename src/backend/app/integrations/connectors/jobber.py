import logging
from datetime import datetime

import httpx

from app.integrations.canonical import (
    CanonicalAsset,
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

JOBBER_API_BASE = "https://api.getjobber.com/api"
JOBBER_AUTH_BASE = "https://api.getjobber.com/api/oauth"


class JobberNormalizer(BaseNormalizer):
    def normalize_customer(self, raw: dict) -> CanonicalCustomer:
        node = raw.get("node", raw)
        addresses = node.get("addresses", [])
        primary_addr = addresses[0] if addresses else {}
        return CanonicalCustomer(
            external_system="jobber",
            external_id=str(node.get("id", "")),
            name=node.get("name", node.get("companyName", "")),
            email=node.get("emails", [{}])[0].get("address") if node.get("emails") else None,
            phone=node.get("phones", [{}])[0].get("number") if node.get("phones") else None,
            address_line1=primary_addr.get("street", primary_addr.get("street1")),
            city=primary_addr.get("city"),
            state=primary_addr.get("province", primary_addr.get("state")),
            postal_code=primary_addr.get("postalCode", primary_addr.get("zip")),
            notes=node.get("description"),
            raw_data=raw,
        )

    def normalize_job(self, raw: dict) -> CanonicalJob:
        node = raw.get("node", raw)
        client = node.get("client", node.get("customer", {})) or {}
        return CanonicalJob(
            external_system="jobber",
            external_id=str(node.get("id", "")),
            customer_external_id=str(client.get("id", "")),
            title=node.get("title", node.get("name", "")),
            description=node.get("description", node.get("instructions", "")),
            status=node.get("status", {}).get("name", "").lower() if isinstance(node.get("status"), dict) else str(node.get("status", "")),
            scheduled_start=_parse_datetime(node.get("startAt")),
            scheduled_end=_parse_datetime(node.get("finishAt")),
            address_line1=node.get("siteAddress", {}).get("street") if node.get("siteAddress") else None,
            city=node.get("siteAddress", {}).get("city") if node.get("siteAddress") else None,
            assigned_employee_external_id=_extract_employee_id(node),
            notes=node.get("description"),
            raw_data=raw,
        )

    def normalize_work_order(self, raw: dict) -> CanonicalWorkOrder:
        node = raw.get("node", raw)
        return CanonicalWorkOrder(
            external_system="jobber",
            external_id=str(node.get("id", "")),
            title=node.get("title", node.get("name", "")),
            description=node.get("instructions", node.get("description", "")),
            status=_status_name(node.get("status")),
            line_items=_extract_line_items(node),
            notes=node.get("description"),
            raw_data=raw,
        )

    def normalize_invoice(self, raw: dict) -> CanonicalInvoice:
        node = raw.get("node", raw)
        client = node.get("client", node.get("customer", {})) or {}
        return CanonicalInvoice(
            external_system="jobber",
            external_id=str(node.get("id", "")),
            customer_external_id=str(client.get("id", "")),
            invoice_number=node.get("invoiceNumber", node.get("number", "")),
            status=node.get("status", {}).get("name", "").lower() if isinstance(node.get("status"), dict) else str(node.get("status", "")),
            subtotal=node.get("subTotal"),
            tax=node.get("taxAmount", node.get("tax")),
            total=node.get("total", node.get("totalAmount")),
            issued_date=_parse_datetime(node.get("issuedAt", node.get("createdAt"))),
            due_date=_parse_datetime(node.get("dueAt", node.get("dueDate"))),
            line_items=_extract_line_items(node),
            notes=node.get("notes"),
            raw_data=raw,
        )

    def normalize_payment(self, raw: dict) -> CanonicalPayment:
        node = raw.get("node", raw)
        return CanonicalPayment(
            external_system="jobber",
            external_id=str(node.get("id", "")),
            amount=node.get("amount"),
            payment_method=node.get("paymentMethod", {}).get("name") if isinstance(node.get("paymentMethod"), dict) else node.get("paymentMethod"),
            payment_date=_parse_datetime(node.get("paidAt", node.get("createdAt"))),
            transaction_reference=node.get("reference", node.get("transactionNumber")),
            raw_data=raw,
        )

    def normalize_employee(self, raw: dict) -> CanonicalEmployee:
        node = raw.get("node", raw)
        name = node.get("name", "")
        parts = name.split(" ", 1) if name else ["", ""]
        return CanonicalEmployee(
            external_system="jobber",
            external_id=str(node.get("id", "")),
            first_name=node.get("firstName", parts[0]),
            last_name=node.get("lastName", parts[1] if len(parts) > 1 else ""),
            email=node.get("emails", [{}])[0].get("address") if node.get("emails") else node.get("email"),
            phone=node.get("phones", [{}])[0].get("number") if node.get("phones") else node.get("phone"),
            role=node.get("type", {}).get("name") if isinstance(node.get("type"), dict) else node.get("role"),
            is_active=node.get("isActive", True),
            raw_data=raw,
        )

    def normalize_asset(self, raw: dict) -> CanonicalAsset:
        node = raw.get("node", raw)
        return CanonicalAsset(
            external_system="jobber",
            external_id=str(node.get("id", "")),
            name=node.get("name", ""),
            asset_type=node.get("assetType", node.get("type")),
            serial_number=node.get("serialNumber", node.get("serial")),
            status=node.get("status", {}).get("name") if isinstance(node.get("status"), dict) else node.get("status"),
            notes=node.get("description"),
            raw_data=raw,
        )

    def normalize_schedule_event(self, raw: dict) -> CanonicalScheduleEvent:
        node = raw.get("node", raw)
        return CanonicalScheduleEvent(
            external_system="jobber",
            external_id=str(node.get("id", "")),
            title=node.get("title", node.get("name", "")),
            start_time=_parse_datetime(node.get("startAt")),
            end_time=_parse_datetime(node.get("finishAt")),
            employee_external_id=_extract_employee_id(node),
            job_external_id=str(node.get("visit", {}).get("id", "")) if node.get("visit") else None,
            status=node.get("status", {}).get("name") if isinstance(node.get("status"), dict) else node.get("status"),
            raw_data=raw,
        )


def _parse_datetime(val) -> datetime | None:
    if not val:
        return None
    try:
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _status_name(status) -> str | None:
    if status is None:
        return None
    if isinstance(status, dict):
        return status.get("name", "").lower()
    return str(status).lower()


def _extract_employee_id(node: dict) -> str | None:
    employees = node.get("employees", [])
    if employees:
        first = employees[0]
        if isinstance(first, dict):
            return str(first.get("id", ""))
        return str(first)
    assignee = node.get("assignedTo", node.get("assignedEmployee", {}))
    if assignee and isinstance(assignee, dict):
        return str(assignee.get("id", ""))
    return None


def _extract_line_items(node: dict) -> list[dict]:
    items = node.get("lineItems", node.get("visitLineItems", []))
    return [
        {
            "name": item.get("name", item.get("title", "")),
            "description": item.get("description", ""),
            "quantity": item.get("quantity", 1),
            "unit_price": item.get("unitPrice", item.get("rate", 0)),
            "total": item.get("total", 0),
            "source_id": str(item.get("id", "")),
        }
        for item in items
    ]


class JobberConnector(BaseConnector):
    provider = "jobber"
    display_name = "Jobber"
    category = ProviderCategory.FIELD_SERVICE
    status = ConnectorStatus.PRODUCTION
    description = "Import customers, jobs, invoices, payments, employees, and schedules from Jobber."
    docs_url = "https://developer.getjobber.com/docs/"
    auth_type = "oauth2"
    scopes: list[str] = ("read",)

    def __init__(self, connection=None):
        super().__init__(connection)
        self._normalizer = JobberNormalizer()
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
            if self.connection:
                self._access_token = self.connection.access_token

    async def _post(self, query: str, variables: dict | None = None) -> dict:
        await self._ensure_client()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "X-JOBBER-GRAPHQL-VERSION": "2023-11-15",
        }
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        response = await self._client.post(f"{JOBBER_API_BASE}/graphql", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            errors = data["errors"]
            raise RuntimeError(f"Jobber GraphQL errors: {errors}")
        return data.get("data", {})

    async def _paginate(self, query: str, result_path: str, variables: dict | None = None) -> list[dict]:
        if variables is None:
            variables = {}
        all_nodes = []
        variables["first"] = 100
        has_next = True
        while has_next:
            data = await self._post(query, variables)
            connection = data
            for key in result_path.split("."):
                connection = connection.get(key, {}) if isinstance(connection, dict) else {}
            nodes = connection.get("nodes", [])
            page_info = connection.get("pageInfo", {})
            all_nodes.extend(nodes)
            has_next = page_info.get("hasNextPage", False)
            if has_next:
                variables["after"] = page_info.get("endCursor")
        return all_nodes

    async def authenticate(self) -> bool:
        if self.connection and self.connection.access_token:
            try:
                await self._ensure_client()
                query = "query { currentAccount { id name } }"
                await self._post(query)
                return True
            except Exception as e:
                logger.warning("Jobber authentication failed: %s", e)
                return False
        return False

    async def fetch_customers(self) -> list[CanonicalCustomer]:
        query = """
        query Clients($first: Int, $after: String) {
          clients(first: $first, after: $after) {
            nodes { id name companyName emails { address } phones { number }
              addresses { street city province postalCode }
              description }
            pageInfo { hasNextPage endCursor }
          }
        }
        """
        nodes = await self._paginate(query, "clients")
        return [self._normalizer.normalize_customer({"node": n}) for n in nodes]

    async def fetch_jobs(self) -> list[CanonicalJob]:
        query = """
        query Visits($first: Int, $after: String) {
          visits(first: $first, after: $after) {
            nodes { id title instructions status { name } startAt finishAt
              client { id } siteAddress { street city }
              employees { id } description }
            pageInfo { hasNextPage endCursor }
          }
        }
        """
        nodes = await self._paginate(query, "visits")
        return [self._normalizer.normalize_job({"node": n}) for n in nodes]

    async def fetch_work_orders(self) -> list[CanonicalWorkOrder]:
        query = """
        query WorkOrders($first: Int, $after: String) {
          workOrders(first: $first, after: $after) {
            nodes { id title instructions status { name }
              lineItems { name quantity unitPrice total }
              description }
            pageInfo { hasNextPage endCursor }
          }
        }
        """
        nodes = await self._paginate(query, "workOrders")
        return [self._normalizer.normalize_work_order({"node": n}) for n in nodes]

    async def fetch_invoices(self) -> list[CanonicalInvoice]:
        query = """
        query Invoices($first: Int, $after: String) {
          invoices(first: $first, after: $after) {
            nodes { id invoiceNumber status { name } subTotal taxAmount total
              issuedAt dueAt client { id }
              lineItems { name quantity unitPrice total }
              notes }
            pageInfo { hasNextPage endCursor }
          }
        }
        """
        nodes = await self._paginate(query, "invoices")
        return [self._normalizer.normalize_invoice({"node": n}) for n in nodes]

    async def fetch_payments(self) -> list[CanonicalPayment]:
        query = """
        query Payments($first: Int, $after: String) {
          payments(first: $first, after: $after) {
            nodes { id amount paymentMethod { name } paidAt
              reference }
            pageInfo { hasNextPage endCursor }
          }
        }
        """
        nodes = await self._paginate(query, "payments")
        return [self._normalizer.normalize_payment({"node": n}) for n in nodes]

    async def fetch_employees(self) -> list[CanonicalEmployee]:
        query = """
        query Employees($first: Int, $after: String) {
          employees(first: $first, after: $after) {
            nodes { id firstName lastName name
              emails { address } phones { number }
              type { name } isActive }
            pageInfo { hasNextPage endCursor }
          }
        }
        """
        nodes = await self._paginate(query, "employees")
        return [self._normalizer.normalize_employee({"node": n}) for n in nodes]

    async def fetch_assets(self) -> list[CanonicalAsset]:
        query = """
        query Assets($first: Int, $after: String) {
          assets(first: $first, after: $after) {
            nodes { id name assetType serialNumber
              status { name } description }
            pageInfo { hasNextPage endCursor }
          }
        }
        """
        nodes = await self._paginate(query, "assets")
        return [self._normalizer.normalize_asset({"node": n}) for n in nodes]

    async def fetch_schedule_events(self) -> list[CanonicalScheduleEvent]:
        query = """
        query CalendarEvents($first: Int, $after: String) {
          calendarEvents(first: $first, after: $after) {
            nodes { id title startAt finishAt
              employees { id } visit { id }
              status { name } }
            pageInfo { hasNextPage endCursor }
          }
        }
        """
        nodes = await self._paginate(query, "calendarEvents")
        return [self._normalizer.normalize_schedule_event({"node": n}) for n in nodes]

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
