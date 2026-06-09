import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class FailureCategory(StrEnum):
    VALIDATION_FAILED = "validation_failed"
    AI_UNAVAILABLE = "ai_unavailable"
    TIMEOUT = "timeout"
    WORKER_CRASH = "worker_crash"
    JOB_NOT_FOUND = "job_not_found"
    DUPLICATE_RACE = "duplicate_race"
    UNKNOWN = "unknown"


class ClassifiedFailure:
    def __init__(
        self,
        category: FailureCategory,
        message: str,
        trace_id: str | None = None,
        job_id: str | None = None,
        company_id: str | None = None,
    ):
        self.category = category
        self.message = message
        self.trace_id = trace_id
        self.job_id = job_id
        self.company_id = company_id


def classify_failure(error_message: str) -> FailureCategory:
    if not error_message:
        return FailureCategory.UNKNOWN
    msg_lower = error_message.lower()
    if "validation failed" in msg_lower or "non_recoverable" in msg_lower:
        return FailureCategory.VALIDATION_FAILED
    if "timeout" in msg_lower:
        return FailureCategory.TIMEOUT
    if "not found" in msg_lower:
        return FailureCategory.JOB_NOT_FOUND
    if "ai_unavailable" in msg_lower or "circuit breaker" in msg_lower or "fallback" in msg_lower:
        return FailureCategory.AI_UNAVAILABLE
    if "duplicate" in msg_lower or "race" in msg_lower:
        return FailureCategory.DUPLICATE_RACE
    if "worker" in msg_lower or "celery" in msg_lower:
        return FailureCategory.WORKER_CRASH
    return FailureCategory.UNKNOWN


def format_failure_for_trace(error_message: str, category: FailureCategory | None = None) -> str:
    cat = category or classify_failure(error_message)
    return f"[{cat.value}] {error_message[:1500]}"


def classify_and_format(error_message: str) -> str:
    return format_failure_for_trace(error_message)
