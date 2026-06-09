from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.pricing.engine import (
    LINE_ITEM_TYPES,
    compute_line_item_total,
)


class LineItemCreate(BaseModel):
    name: str
    item_type: str = "labor"
    quantity: float = 1.0
    rate: float = 0.0
    total: float = 0.0
    sort_order: int = 0
    override_reason: str | None = None

    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v):
        if v not in LINE_ITEM_TYPES:
            raise ValueError(f"item_type must be one of {LINE_ITEM_TYPES}, got '{v}'")
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v):
        if v < 0:
            raise ValueError(f"quantity must be >= 0, got {v}")
        return v

    @field_validator("rate")
    @classmethod
    def validate_rate(cls, v):
        if v < 0:
            raise ValueError(f"rate must be >= 0, got {v}")
        return v

    @model_validator(mode="after")
    def validate_total(self):
        computed = compute_line_item_total(self.quantity, self.rate)
        if abs(self.total - computed) > 0.02:
            raise ValueError(
                f"total {self.total} does not match computed total {computed} ({self.quantity} * {self.rate})"
            )
        return self


class LineItemResponse(BaseModel):
    id: UUID
    estimate_id: UUID
    name: str
    item_type: str
    quantity: float
    rate: float
    total: float
    sort_order: int
    ai_quantity: float | None = None
    ai_rate: float | None = None
    ai_total: float | None = None
    override_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EstimateGenerateRequest(BaseModel):
    job_id: UUID
    customer_id: UUID | None = None
    description: str | None = None

    @field_validator("description")
    @classmethod
    def validate_description_length(cls, v):
        if v is not None and len(v) > 10000:
            raise ValueError("description must be at most 10000 characters")
        return v


class EstimateUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    notes: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    line_items: list[LineItemCreate] | None = None

    @field_validator("subtotal")
    @classmethod
    def validate_subtotal_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError(f"subtotal must be >= 0, got {v}")
        return v

    @field_validator("tax")
    @classmethod
    def validate_tax_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError(f"tax must be >= 0, got {v}")
        return v

    @model_validator(mode="after")
    def validate_totals(self):
        if self.line_items and self.subtotal is not None:
            from app.pricing.engine import compute_subtotal

            items = [li.model_dump() for li in self.line_items]
            computed_subtotal = compute_subtotal(items)
            if abs(self.subtotal - computed_subtotal) > 0.02:
                raise ValueError(f"subtotal {self.subtotal} does not match computed subtotal {computed_subtotal}")
        if self.subtotal is not None and self.tax is not None and self.total is not None:
            from app.pricing.engine import compute_total

            computed_total = compute_total(self.subtotal, self.tax)
            if abs(self.total - computed_total) > 0.02:
                raise ValueError(
                    f"total {self.total} does not match computed total {computed_total} "
                    f"(subtotal={self.subtotal} + tax={self.tax})"
                )
        return self


class EstimateResponse(BaseModel):
    id: UUID
    company_id: UUID
    job_id: UUID | None = None
    customer_id: UUID | None = None
    status: str
    title: str | None = None
    description: str | None = None
    subtotal: float
    tax: float
    total: float
    confidence_score: float
    assumptions: list
    notes: str | None = None
    ai_generated: bool
    approved_at: datetime | None = None
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    line_items: list[LineItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class EstimateListResponse(BaseModel):
    estimates: list[EstimateResponse]
    total: int


class CompanyPricingBrainResponse(BaseModel):
    company_id: UUID
    trade_type: str | None = None
    labor_rates: dict
    service_fee: float
    minimum_charge_hours: float
    rounding_rule: str
    markup_percent: float
    emergency_multiplier: float
    after_hours_multiplier: float
    estimation_style: str
    historical_data_enabled: bool

    model_config = ConfigDict(from_attributes=True)


class ServiceCreate(BaseModel):
    name: str
    avg_time_hours: float = 1.0
    pricing_type: str = "hourly"
    flat_rate: float | None = None
    material_assumptions: list = []


class ServiceResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    avg_time_hours: float
    pricing_type: str
    flat_rate: float | None = None
    material_assumptions: list

    model_config = ConfigDict(from_attributes=True)


class CompanyPricingBrainUpdate(BaseModel):
    trade_type: str | None = None
    labor_rates: dict | None = None
    service_fee: float | None = None
    minimum_charge_hours: float | None = None
    rounding_rule: str | None = None
    markup_percent: float | None = None
    emergency_multiplier: float | None = None
    after_hours_multiplier: float | None = None
    estimation_style: str | None = None
    historical_data_enabled: bool | None = None

    @field_validator("markup_percent")
    @classmethod
    def validate_markup(cls, v):
        if v is not None and (v < 0 or v > 500):
            raise ValueError(f"markup_percent must be between 0 and 500, got {v}")
        return v

    @field_validator("emergency_multiplier")
    @classmethod
    def validate_emergency_multiplier(cls, v):
        if v is not None and (v < 1.0 or v > 10.0):
            raise ValueError(f"emergency_multiplier must be between 1.0 and 10.0, got {v}")
        return v

    @field_validator("after_hours_multiplier")
    @classmethod
    def validate_after_hours(cls, v):
        if v is not None and (v < 1.0 or v > 5.0):
            raise ValueError(f"after_hours_multiplier must be between 1.0 and 5.0, got {v}")
        return v

    @field_validator("minimum_charge_hours")
    @classmethod
    def validate_minimum_charge(cls, v):
        if v is not None and (v < 0 or v > 24):
            raise ValueError(f"minimum_charge_hours must be between 0 and 24, got {v}")
        return v

    @field_validator("labor_rates")
    @classmethod
    def validate_labor_rates(cls, v):
        if v is not None:
            for trade, rate in v.items():
                if not isinstance(rate, (int, float)):
                    raise ValueError(f"labor_rate for '{trade}' must be a number, got {rate}")
                if rate < 0 or rate > 10000:
                    raise ValueError(f"labor_rate for '{trade}' must be between 0 and 10000, got {rate}")
        return v

    @field_validator("rounding_rule")
    @classmethod
    def validate_rounding_rule(cls, v):
        if v is not None and v not in ("nearest_dollar", "30_min", "15_min", "hourly", "exact"):
            raise ValueError(f"rounding_rule must be one of: nearest_dollar, 30_min, 15_min, hourly, exact, got '{v}'")
        return v

    @field_validator("service_fee")
    @classmethod
    def validate_service_fee(cls, v):
        if v is not None and (v < 0 or v > 10000):
            raise ValueError(f"service_fee must be between 0 and 10000, got {v}")
        return v


class HistoricalJobRecord(BaseModel):
    service_type: str
    estimated_hours: float
    actual_hours: float
    estimated_cost: float
    actual_cost: float
    materials_used: list = []
    final_invoice_amount: float
    technician_notes: str | None = None
