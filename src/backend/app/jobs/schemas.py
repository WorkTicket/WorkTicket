from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobCreate(BaseModel):
    customer_id: UUID
    technician_id: str | None = None
    scheduled_time: datetime | None = None
    description: str | None = None
    address: str | None = None


class JobResponse(BaseModel):
    id: UUID
    company_id: UUID
    customer_id: UUID
    technician_id: str
    status: str
    scheduled_time: datetime | None = None
    description: str | None = None
    address: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int


class CustomerCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None


class CustomerResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CustomerListResponse(BaseModel):
    customers: list[CustomerResponse]
    total: int
    page: int
    page_size: int


class JobUpdate(BaseModel):
    description: str | None = None
    address: str | None = None
    status: str | None = None
    scheduled_time: datetime | None = None
    customer_id: str | None = None
    technician_id: str | None = None
