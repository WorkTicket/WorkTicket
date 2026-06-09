from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BillingAccountResponse(BaseModel):
    company_id: UUID
    plan: str
    monthly_quota_acu: float
    used_acu: float
    reserved_acu: float
    overage_enabled: bool
    ai_disabled: bool
    risk_score: int
    reservation_heartbeat_at: datetime | None = None
    billing_period_start: datetime | None = None
    billing_period_end: datetime | None = None
    reset_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UsageLedgerEntry(BaseModel):
    id: UUID
    company_id: UUID
    job_id: UUID | None = None
    text_units: int
    vision_units: int
    audio_units: int
    cost_usd: float
    estimated_cost_usd: float
    model_used: str | None = None
    execution_time_ms: int | None = None
    is_credit: bool = False
    credit_reason: str | None = None
    original_job_id: UUID | None = None
    billing_period: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsageLedgerListResponse(BaseModel):
    entries: list[UsageLedgerEntry]
    total: int
    page: int
    page_size: int


class UsageSummaryResponse(BaseModel):
    company_id: UUID
    plan: str
    quota_total: float
    quota_used: float
    quota_remaining: float
    quota_reserved: float
    usage_percent: float
    ai_disabled: bool
    reset_at: datetime | None = None


class CostEstimateResponse(BaseModel):
    estimated_text_cost: float
    estimated_vision_cost: float
    estimated_audio_cost: float
    estimated_total_cost: float
    within_quota: bool
    quota_remaining_after: float


class ChangePlanRequest(BaseModel):
    plan: str


class BillingAdminResponse(BaseModel):
    id: UUID
    company_id: UUID
    cost_usd: float
    model_used: str | None = None
    execution_time_ms: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TierConfig(BaseModel):
    quota_acu: float
    max_cost_per_job: float
    routing: str
    concurrency_limit: int
    price_monthly: float


class CreditGrantRequest(BaseModel):
    job_id: UUID
    amount_acu: float = Field(gt=0, description="Amount of ACU to credit back")
    reason: str = Field(min_length=1, max_length=500)


class CreditGrantResponse(BaseModel):
    status: str
    company_id: str
    job_id: str
    amount_acu: float
    reason: str
    used_acu_after: float


class CostDriftResponse(BaseModel):
    total_jobs: int
    total_estimated_cost: float
    total_actual_cost: float
    drift_pct: float
    avg_estimation_error_pct: float
    time_window_hours: int
