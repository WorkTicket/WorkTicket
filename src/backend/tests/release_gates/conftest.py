"""Release Gate A — Shared fixtures for integration migration validation.

Mock provider framework that simulates real provider behavior:
- Pagination across multiple pages
- Configurable rate limiting with 429 responses
- Failure injection at specific record indices
- Malformed record generation
- Duplicate record simulation

All mocks implement the full BaseConnector contract.
"""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

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
    ConnectionHealth,
    ConnectorStatus,
    ProviderCategory,
)

TEST_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TENANT_B_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _generate_customer(i: int, malformed: bool = False) -> CanonicalCustomer:
    if malformed:
        return CanonicalCustomer(
            external_system="mock_quickbooks",
            external_id=f"qb-cust-{i:06d}",
            name=None,
            email=f"bad-email-{i}",
            phone=None,
        )
    return CanonicalCustomer(
        external_system="mock_quickbooks",
        external_id=f"qb-cust-{i:06d}",
        name=f"Customer {i}",
        email=f"customer{i}@example.com",
        phone=f"+1-555-{i:04d}",
        address_line1=f"{i} Main St",
        city="Springfield",
        state="IL",
        postal_code="62701",
        notes=f"Notes for customer {i}",
    )


def _generate_invoice(i: int, malformed: bool = False) -> CanonicalInvoice:
    if malformed:
        return CanonicalInvoice(
            external_system="mock_quickbooks",
            external_id=f"qb-inv-{i:06d}",
            total=None,
            status=None,
        )
    return CanonicalInvoice(
        external_system="mock_quickbooks",
        external_id=f"qb-inv-{i:06d}",
        customer_external_id=f"qb-cust-{i:06d}",
        invoice_number=f"INV-{i:06d}",
        status="sent" if i % 3 != 0 else "paid",
        subtotal=100.00 + i,
        tax=8.50,
        total=108.50 + i,
        currency="USD",
        issued_date=datetime(2026, 1, 1, tzinfo=UTC),
        due_date=datetime(2026, 2, 1, tzinfo=UTC),
    )


def _generate_payment(i: int) -> CanonicalPayment:
    return CanonicalPayment(
        external_system="mock_stripe",
        external_id=f"stripe-pi-{i:06d}",
        customer_external_id=f"stripe-cust-{i:06d}",
        amount=108.50 + (i % 10),
        currency="USD",
        payment_method="card",
        status="succeeded",
        payment_date=datetime(2026, 1, 15, tzinfo=UTC),
        transaction_reference=f"ch_{uuid.uuid4().hex[:16]}",
    )


class _PaginationState:
    def __init__(
        self,
        total_records: int,
        page_size: int = 100,
        rate_limit_pages: set[int] | None = None,
        fail_rate: float = 0.0,
    ):
        self.total = total_records
        self.page_size = page_size
        self.current_page = 0
        self.rate_limit_pages = rate_limit_pages or set()
        self.fail_rate = fail_rate
        self.call_count = 0

    @property
    def total_pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)

    def next_page(self) -> list[int] | None:
        self.call_count += 1
        if self.current_page >= self.total_pages:
            return None
        if self.current_page in self.rate_limit_pages:
            self.current_page += 1
            raise _SimulatedRateLimitError(self.current_page)
        start = self.current_page * self.page_size
        end = min(start + self.page_size, self.total)
        self.current_page += 1
        indices = list(range(start, end))
        if self.fail_rate > 0:
            import random
            rng = random.Random(42)
            indices = [i for i in indices if rng.random() > self.fail_rate]
        return indices


class _SimulatedRateLimitError(Exception):
    pass


class MockQuickBooksConnector(BaseConnector):
    provider = "mock_quickbooks"
    display_name = "QuickBooks (Mock)"
    category = ProviderCategory.ACCOUNTING
    status = ConnectorStatus.PRODUCTION
    auth_type = "oauth2"
    scopes = ("com.intuit.quickbooks.accounting",)

    def __init__(self, connection=None, customers=250, invoices=150, malformed_customers=0, malformed_invoices=0,
                 rate_limit_pages=None, fail_rate=0.0):
        super().__init__(connection)
        self._customers = customers
        self._invoices = invoices
        self._malformed_customers = malformed_customers
        self._malformed_invoices = malformed_invoices
        self._rate_limit_pages = rate_limit_pages or set()
        self._fail_rate = fail_rate
        self.health = ConnectionHealth.HEALTHY

    async def authenticate(self) -> bool:
        if (
            self.connection
            and hasattr(self.connection, "connection_status")
            and hasattr(self.connection.connection_status, "value")
            and self.connection.connection_status.value == "disconnected"
        ):
            self.health = ConnectionHealth.DISCONNECTED
            return False
        self.health = ConnectionHealth.HEALTHY
        return True

    async def _paginated_fetch(self, total: int, generator, malformed: int = 0):
        pagination = _PaginationState(
            total, page_size=50,
            rate_limit_pages=self._rate_limit_pages,
            fail_rate=self._fail_rate,
        )
        results = []
        while True:
            try:
                indices = pagination.next_page()
            except _SimulatedRateLimitError:
                await asyncio.sleep(0.05)
                continue
            if indices is None:
                break
            for i in indices:
                is_malformed = i < malformed
                results.append(generator(i, malformed=is_malformed))
        return results

    async def fetch_customers(self) -> list[CanonicalCustomer]:
        return await self._paginated_fetch(self._customers, _generate_customer, self._malformed_customers)

    async def fetch_invoices(self) -> list[CanonicalInvoice]:
        return await self._paginated_fetch(self._invoices, _generate_invoice, self._malformed_invoices)

    async def fetch_jobs(self) -> list[CanonicalJob]:
        return [
            CanonicalJob(
                external_system="mock_quickbooks",
                external_id=f"qb-job-{i:06d}",
                customer_external_id=f"qb-cust-{i % max(self._customers, 1):06d}",
                title=f"HVAC Repair #{i}",
                description=f"Service call for unit {i}",
                status="scheduled" if i % 3 == 0 else "completed",
            )
            for i in range(min(100, self._customers))
        ]

    async def fetch_work_orders(self) -> list[CanonicalWorkOrder]:
        return []

    async def fetch_payments(self) -> list[CanonicalPayment]:
        return []

    async def fetch_employees(self) -> list[CanonicalEmployee]:
        return [
            CanonicalEmployee(
                external_system="mock_quickbooks",
                external_id=f"qb-emp-{i:06d}",
                first_name=f"Emp{i}",
                last_name=f"Last{i}",
                email=f"emp{i}@company.com",
                role="technician" if i % 2 == 0 else "dispatcher",
            )
            for i in range(50)
        ]

    async def fetch_assets(self) -> list:
        return []

    async def fetch_schedule_events(self) -> list[CanonicalScheduleEvent]:
        return []


class MockJobberConnector(BaseConnector):
    provider = "mock_jobber"
    display_name = "Jobber (Mock)"
    category = ProviderCategory.FIELD_SERVICE
    status = ConnectorStatus.PRODUCTION
    auth_type = "oauth2"
    scopes = ("read",)

    def __init__(self, connection=None, customers=300, jobs=200, invoices=100):
        super().__init__(connection)
        self._customers = customers
        self._jobs = jobs
        self._invoices = invoices
        self.health = ConnectionHealth.HEALTHY

    async def authenticate(self) -> bool:
        return True

    async def fetch_customers(self) -> list[CanonicalCustomer]:
        return [
            CanonicalCustomer(
                external_system="mock_jobber",
                external_id=f"jb-cust-{i:06d}",
                name=f"Jobber Client {i}",
                email=f"jb-client{i}@example.com",
                phone=f"+1-555-{i+1000:04d}",
            )
            for i in range(self._customers)
        ]

    async def fetch_jobs(self) -> list[CanonicalJob]:
        return [
            CanonicalJob(
                external_system="mock_jobber",
                external_id=f"jb-job-{i:06d}",
                customer_external_id=f"jb-cust-{i % max(self._customers, 1):06d}",
                title=f"Landscaping Job {i}",
                status="scheduled",
            )
            for i in range(self._jobs)
        ]

    async def fetch_work_orders(self) -> list[CanonicalWorkOrder]:
        return []

    async def fetch_invoices(self) -> list[CanonicalInvoice]:
        return [
            CanonicalInvoice(
                external_system="mock_jobber",
                external_id=f"jb-inv-{i:06d}",
                customer_external_id=f"jb-cust-{i % max(self._customers, 1):06d}",
                invoice_number=f"JB-{i:06d}",
                status="sent",
                total=200.00 + (i % 50),
            )
            for i in range(self._invoices)
        ]

    async def fetch_payments(self) -> list[CanonicalPayment]:
        return []

    async def fetch_employees(self) -> list[CanonicalEmployee]:
        return []

    async def fetch_assets(self) -> list:
        return []

    async def fetch_schedule_events(self) -> list[CanonicalScheduleEvent]:
        return []


class MockHousecallProConnector(BaseConnector):
    provider = "mock_housecall_pro"
    display_name = "Housecall Pro (Mock)"
    category = ProviderCategory.FIELD_SERVICE
    status = ConnectorStatus.PRODUCTION
    auth_type = "api_key"
    scopes = ("read",)

    def __init__(self, connection=None, customers=200, jobs=150):
        super().__init__(connection)
        self._customers = customers
        self._jobs = jobs
        self.health = ConnectionHealth.HEALTHY

    async def authenticate(self) -> bool:
        return True

    async def fetch_customers(self) -> list[CanonicalCustomer]:
        return [
            CanonicalCustomer(
                external_system="mock_housecall_pro",
                external_id=f"hcp-cust-{i:06d}",
                name=f"HCP Customer {i}",
                email=f"hcp{i}@example.com",
                phone=f"+1-555-{i+2000:04d}",
            )
            for i in range(self._customers)
        ]

    async def fetch_jobs(self) -> list[CanonicalJob]:
        return [
            CanonicalJob(
                external_system="mock_housecall_pro",
                external_id=f"hcp-job-{i:06d}",
                title=f"Plumbing Job {i}",
                status="completed" if i % 2 == 0 else "in_progress",
            )
            for i in range(self._jobs)
        ]

    async def fetch_work_orders(self) -> list[CanonicalWorkOrder]:
        return []

    async def fetch_invoices(self) -> list[CanonicalInvoice]:
        return []

    async def fetch_payments(self) -> list[CanonicalPayment]:
        return []

    async def fetch_employees(self) -> list[CanonicalEmployee]:
        return []

    async def fetch_assets(self) -> list:
        return []

    async def fetch_schedule_events(self) -> list[CanonicalScheduleEvent]:
        return []


class MockStripeConnector(BaseConnector):
    provider = "mock_stripe"
    display_name = "Stripe (Mock)"
    category = ProviderCategory.PAYMENTS
    status = ConnectorStatus.PRODUCTION
    auth_type = "api_key"
    scopes = ("read",)

    def __init__(self, connection=None, payments=300):
        super().__init__(connection)
        self._payments = payments
        self.health = ConnectionHealth.HEALTHY

    async def authenticate(self) -> bool:
        return True

    async def fetch_customers(self) -> list[CanonicalCustomer]:
        return [
            CanonicalCustomer(
                external_system="mock_stripe",
                external_id=f"stripe-cust-{i:06d}",
                name=f"Stripe Customer {i}",
                email=f"stripe{i}@example.com",
            )
            for i in range(200)
        ]

    async def fetch_jobs(self) -> list:
        return []

    async def fetch_work_orders(self) -> list:
        return []

    async def fetch_invoices(self) -> list[CanonicalInvoice]:
        return [
            CanonicalInvoice(
                external_system="mock_stripe",
                external_id=f"stripe-inv-{i:06d}",
                customer_external_id=f"stripe-cust-{i:06d}",
                invoice_number=f"STR-{i:06d}",
                status="paid",
                total=99.99 + (i % 20),
            )
            for i in range(100)
        ]

    async def fetch_payments(self) -> list[CanonicalPayment]:
        return [_generate_payment(i) for i in range(self._payments)]

    async def fetch_employees(self) -> list:
        return []

    async def fetch_assets(self) -> list:
        return []

    async def fetch_schedule_events(self) -> list[CanonicalScheduleEvent]:
        return []


class MockFailingConnector(BaseConnector):
    provider = "mock_failing"
    display_name = "Failing Provider (Mock)"
    category = ProviderCategory.ACCOUNTING
    status = ConnectorStatus.PRODUCTION
    scopes = ("read",)

    def __init__(self, connection=None, fail_at_authenticate=False):
        super().__init__(connection)
        self.fail_at_authenticate = fail_at_authenticate

    async def authenticate(self) -> bool:
        return not self.fail_at_authenticate

    async def fetch_customers(self) -> list[CanonicalCustomer]:
        return [
            CanonicalCustomer(
                external_system="mock_failing",
                external_id=f"fail-cust-{i:06d}",
                name=f"Fail Customer {i}",
            )
            for i in range(1000)
        ]

    async def fetch_jobs(self) -> list:
        return []

    async def fetch_work_orders(self) -> list:
        return []

    async def fetch_invoices(self) -> list:
        return []

    async def fetch_payments(self) -> list:
        return []

    async def fetch_employees(self) -> list:
        return []

    async def fetch_assets(self) -> list:
        return []

    async def fetch_schedule_events(self) -> list:
        return []


MOCK_PROVIDER_REGISTRY = {
    "mock_quickbooks": MockQuickBooksConnector,
    "mock_jobber": MockJobberConnector,
    "mock_housecall_pro": MockHousecallProConnector,
    "mock_stripe": MockStripeConnector,
    "mock_failing": MockFailingConnector,
}


@pytest.fixture(autouse=True)
def register_mock_providers(monkeypatch):
    from app.integrations import registry
    original = dict(registry.PROVIDERS)
    merged = {**original, **MOCK_PROVIDER_REGISTRY}
    monkeypatch.setattr(registry, "PROVIDERS", merged)
    yield
    monkeypatch.setattr(registry, "PROVIDERS", original)


@pytest.fixture
def tenant_b_company():
    return {
        "id": str(TENANT_B_ID),
        "name": "Tenant B Company",
    }
