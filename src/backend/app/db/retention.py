import logging
import os
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

_ANALYTICS_RETENTION_DAYS = int(os.getenv("ANALYTICS_RETENTION_DAYS", "365"))
_AUDIT_LOG_RETENTION_DAYS = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "90"))
_TRACE_RETENTION_DAYS = int(os.getenv("TRACE_RETENTION_DAYS", "30"))
_AI_OUTPUT_RETENTION_DAYS = int(os.getenv("AI_OUTPUT_RETENTION_DAYS", "365"))
_DLQ_RETENTION_DAYS = int(os.getenv("DLQ_RETENTION_DAYS", "30"))


RETENTION_POLICIES = {
    "analytics_events": {
        "retention_days": _ANALYTICS_RETENTION_DAYS,
        "description": "Analytics events used for product metrics and business intelligence",
        "action": "hard_delete",
        "configurable": True,
    },
    "ai_audit_logs": {
        "retention_days": _AUDIT_LOG_RETENTION_DAYS,
        "description": "AI audit trail including request/response metadata and circuit breaker state",
        "action": "hard_delete",
        "configurable": True,
    },
    "execution_traces": {
        "retention_days": _TRACE_RETENTION_DAYS,
        "description": "Distributed tracing spans for debugging and performance analysis",
        "action": "hard_delete",
        "configurable": True,
    },
    "ai_outputs": {
        "retention_days": _AI_OUTPUT_RETENTION_DAYS,
        "description": "AI-generated analysis outputs stored per job",
        "action": "soft_delete",
        "configurable": True,
        "note": "AI outputs are tenant-scoped; retention starts from job completion date",
    },
    "dlq_entries": {
        "retention_days": _DLQ_RETENTION_DAYS,
        "description": "Dead letter queue entries for failed message delivery (SMS, Email)",
        "action": "hard_delete",
        "configurable": True,
    },
}


def get_retention_policy(data_type: str) -> dict:
    return RETENTION_POLICIES.get(data_type, {})


def get_all_policies() -> dict:
    return dict(RETENTION_POLICIES)


def get_cutoff_date(data_type: str) -> datetime:
    policy = get_retention_policy(data_type)
    days = policy.get("retention_days", 365)
    return datetime.now(UTC) - timedelta(days=days)
