from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CanonicalCustomer(BaseModel):
    external_system: str
    external_id: str
    name: str
    email: str | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = "US"
    notes: str | None = None
    raw_data: dict | None = None


class CanonicalInvoice(BaseModel):
    external_system: str
    external_id: str
    customer_external_id: str | None = None
    job_external_id: str | None = None
    invoice_number: str | None = None
    status: str | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    currency: str | None = "USD"
    issued_date: datetime | None = None
    due_date: datetime | None = None
    paid_date: datetime | None = None
    line_items: list[dict] | None = None
    notes: str | None = None
    raw_data: dict | None = None


class CanonicalPayment(BaseModel):
    external_system: str
    external_id: str
    customer_external_id: str | None = None
    invoice_external_id: str | None = None
    amount: Decimal | None = None
    currency: str | None = "USD"
    payment_method: str | None = None
    status: str | None = None
    payment_date: datetime | None = None
    transaction_reference: str | None = None
    notes: str | None = None
    raw_data: dict | None = None


class CanonicalJob(BaseModel):
    external_system: str
    external_id: str
    customer_external_id: str | None = None
    title: str | None = None
    description: str | None = None
    status: str | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    assigned_employee_external_id: str | None = None
    priority: str | None = None
    notes: str | None = None
    raw_data: dict | None = None


class CanonicalWorkOrder(BaseModel):
    external_system: str
    external_id: str
    job_external_id: str | None = None
    customer_external_id: str | None = None
    title: str | None = None
    description: str | None = None
    status: str | None = None
    scheduled_date: datetime | None = None
    completed_date: datetime | None = None
    assigned_employee_external_id: str | None = None
    line_items: list[dict] | None = None
    notes: str | None = None
    raw_data: dict | None = None


class CanonicalEmployee(BaseModel):
    external_system: str
    external_id: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str | None = None
    hire_date: datetime | None = None
    hourly_rate: Decimal | None = None
    is_active: bool | None = True
    notes: str | None = None
    raw_data: dict | None = None


class CanonicalAsset(BaseModel):
    external_system: str
    external_id: str
    name: str | None = None
    asset_type: str | None = None
    serial_number: str | None = None
    status: str | None = None
    assigned_employee_external_id: str | None = None
    location_external_id: str | None = None
    purchase_date: datetime | None = None
    notes: str | None = None
    raw_data: dict | None = None


class CanonicalLocation(BaseModel):
    external_system: str
    external_id: str
    name: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = "US"
    latitude: float | None = None
    longitude: float | None = None
    location_type: str | None = None
    notes: str | None = None
    raw_data: dict | None = None


class CanonicalScheduleEvent(BaseModel):
    external_system: str
    external_id: str
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    employee_external_id: str | None = None
    job_external_id: str | None = None
    customer_external_id: str | None = None
    event_type: str | None = None
    status: str | None = None
    recurrence_rule: str | None = None
    notes: str | None = None
    raw_data: dict | None = None


CANONICAL_MODEL_MAP = {
    "customers": CanonicalCustomer,
    "jobs": CanonicalJob,
    "work_orders": CanonicalWorkOrder,
    "invoices": CanonicalInvoice,
    "payments": CanonicalPayment,
    "employees": CanonicalEmployee,
    "assets": CanonicalAsset,
    "locations": CanonicalLocation,
    "schedule_events": CanonicalScheduleEvent,
}
