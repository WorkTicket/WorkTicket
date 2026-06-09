
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


class BaseNormalizer:
    """Normalizes raw provider data into canonical models.

    Normalizers transform provider-specific field names and values
    into the canonical schema. Each connector should have its own normalizer.
    """

    def normalize_customer(self, raw: dict) -> CanonicalCustomer:
        raise NotImplementedError

    def normalize_job(self, raw: dict) -> CanonicalJob:
        raise NotImplementedError

    def normalize_work_order(self, raw: dict) -> CanonicalWorkOrder:
        raise NotImplementedError

    def normalize_invoice(self, raw: dict) -> CanonicalInvoice:
        raise NotImplementedError

    def normalize_payment(self, raw: dict) -> CanonicalPayment:
        raise NotImplementedError

    def normalize_employee(self, raw: dict) -> CanonicalEmployee:
        raise NotImplementedError

    def normalize_asset(self, raw: dict) -> CanonicalAsset:
        raise NotImplementedError

    def normalize_schedule_event(self, raw: dict) -> CanonicalScheduleEvent:
        raise NotImplementedError


class DefaultNormalizer(BaseNormalizer):
    """Default pass-through normalizer that expects data already in canonical form."""

    def normalize_customer(self, raw: dict) -> CanonicalCustomer:
        return CanonicalCustomer(**raw)

    def normalize_job(self, raw: dict) -> CanonicalJob:
        return CanonicalJob(**raw)

    def normalize_work_order(self, raw: dict) -> CanonicalWorkOrder:
        return CanonicalWorkOrder(**raw)

    def normalize_invoice(self, raw: dict) -> CanonicalInvoice:
        return CanonicalInvoice(**raw)

    def normalize_payment(self, raw: dict) -> CanonicalPayment:
        return CanonicalPayment(**raw)

    def normalize_employee(self, raw: dict) -> CanonicalEmployee:
        return CanonicalEmployee(**raw)

    def normalize_asset(self, raw: dict) -> CanonicalAsset:
        return CanonicalAsset(**raw)

    def normalize_schedule_event(self, raw: dict) -> CanonicalScheduleEvent:
        return CanonicalScheduleEvent(**raw)
