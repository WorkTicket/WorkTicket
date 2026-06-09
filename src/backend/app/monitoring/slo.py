"""RTO/RPO definitions and SLO/SLI configuration for WorkTicket.

This module defines the service level objectives, indicators, and
recovery targets. Consumed by monitoring dashboards and incident
response runbooks.

Targets:
    Availability: 99.9% (error budget: 43.2 min/month)
    Latency P95: 500ms
    Latency P99: 2000ms
    RTO (Recovery Time Objective): 1 hour
    RPO (Recovery Point Objective): 5 minutes
"""

from dataclasses import dataclass


@dataclass
class SLIDefinition:
    name: str
    description: str
    unit: str
    target: float
    window: str  # e.g., "30d", "7d", "24h"


@dataclass
class SLODefinition:
    name: str
    description: str
    target: float  # e.g., 0.999 for 99.9%
    slis: list[str]


@dataclass
class RecoveryObjective:
    metric: str
    target: str
    description: str


# --- Recovery Time & Point Objectives (RTO/RPO) ---

RTO = RecoveryObjective(
    metric="recovery_time",
    target="1 hour",
    description=(
        "Maximum acceptable time to restore service after a complete outage. "
        "Measured from incident declaration to full service restoration. "
        "Excludes detection time (target: < 5 minutes via Prometheus Alertmanager)."
    ),
)

RPO = RecoveryObjective(
    metric="recovery_point",
    target="5 minutes",
    description=(
        "Maximum acceptable data loss measured in time. "
        "Achieved via PostgreSQL continuous WAL archiving with 5-minute "
        "archive_timeout. Full backups performed daily at 02:00 UTC."
    ),
)

# --- Service Level Indicators (SLIs) ---

SLIS = [
    SLIDefinition(
        name="availability",
        description="Fraction of successful (non-5xx) HTTP responses",
        unit="fraction",
        target=0.999,
        window="30d",
    ),
    SLIDefinition(
        name="latency_p95",
        description="95th percentile HTTP request latency",
        unit="milliseconds",
        target=500,
        window="30d",
    ),
    SLIDefinition(
        name="latency_p99",
        description="99th percentile HTTP request latency",
        unit="milliseconds",
        target=2000,
        window="30d",
    ),
    SLIDefinition(
        name="error_rate",
        description="Fraction of requests resulting in 5xx errors",
        unit="fraction",
        target=0.001,
        window="30d",
    ),
    SLIDefinition(
        name="db_availability",
        description="Fraction of successful database health checks",
        unit="fraction",
        target=0.9995,
        window="30d",
    ),
    SLIDefinition(
        name="redis_availability",
        description="Fraction of successful Redis health checks",
        unit="fraction",
        target=0.9995,
        window="30d",
    ),
    SLIDefinition(
        name="celery_queue_health",
        description="Fraction of time Celery queues are below backpressure threshold",
        unit="fraction",
        target=0.99,
        window="30d",
    ),
    SLIDefinition(
        name="ai_availability",
        description="Fraction of AI requests that succeed (vs fallback)",
        unit="fraction",
        target=0.95,
        window="30d",
    ),
    SLIDefinition(
        name="webhook_processing_success",
        description="Fraction of Stripe webhooks successfully processed",
        unit="fraction",
        target=0.999,
        window="30d",
    ),
    SLIDefinition(
        name="health_endpoint_availability",
        description="Fraction of successful health endpoint probes (healthz/readyz/livez)",
        unit="fraction",
        target=0.9999,
        window="30d",
    ),
    SLIDefinition(
        name="health_endpoint_latency_p95",
        description="95th percentile health endpoint latency",
        unit="milliseconds",
        target=200,
        window="30d",
    ),
    SLIDefinition(
        name="websocket_message_latency_p95",
        description="95th percentile WebSocket message delivery latency",
        unit="milliseconds",
        target=1000,
        window="30d",
    ),
    SLIDefinition(
        name="email_delivery_latency_p95",
        description="95th percentile email delivery latency (Resend API)",
        unit="milliseconds",
        target=5000,
        window="30d",
    ),
]

# --- Service Level Objectives (SLOs) ---

SLOS = [
    SLODefinition(
        name="api_availability",
        description="WorkTicket API availability",
        target=0.999,
        slis=["availability"],
    ),
    SLODefinition(
        name="api_latency",
        description="API response latency within acceptable range",
        target=0.95,  # 95% of requests under P95 target
        slis=["latency_p95"],
    ),
    SLODefinition(
        name="data_durability",
        description="No unrecoverable data loss within RPO window",
        target=1.0,
        slis=["db_availability"],
    ),
    SLODefinition(
        name="ai_service_quality",
        description="AI service operational without fallback",
        target=0.95,
        slis=["ai_availability"],
    ),
    SLODefinition(
        name="payment_processing",
        description="Stripe webhook processing reliability",
        target=0.999,
        slis=["webhook_processing_success"],
    ),
    SLODefinition(
        name="health_endpoints",
        description="Health check endpoint availability and performance",
        target=0.9999,
        slis=["health_endpoint_availability", "health_endpoint_latency_p95"],
    ),
    SLODefinition(
        name="websocket_performance",
        description="WebSocket message delivery latency",
        target=0.95,
        slis=["websocket_message_latency_p95"],
    ),
    SLODefinition(
        name="email_delivery",
        description="Email delivery reliability and latency",
        target=0.99,
        slis=["email_delivery_latency_p95"],
    ),
]

# --- Error Budgets (per 30-day window) ---

ERROR_BUDGETS = {
    "api_availability": {
        "total_minutes": 43200,  # 30 days in minutes
        "allowed_downtime_minutes": 43.2,  # 0.1% of 30 days
        "description": "43.2 minutes of downtime per 30 days",
    },
    "api_latency": {
        "total_requests_30d": "dependent_on_traffic",
        "allowed_slow_requests_pct": 5.0,
        "description": "5% of requests may exceed P95 latency target",
    },
}

# --- Composite Health Score ---


def calculate_health_score(availability: float, error_rate: float, latency_p95_ms: float) -> dict:
    """Calculate a composite health score from 0-100 based on SLIs.

    Args:
        availability: Current availability fraction (0-1)
        error_rate: Current error rate fraction (0-1)
        latency_p95_ms: Current P95 latency in ms

    Returns:
        Dict with score and component breakdowns
    """
    avail_score = min(100, (availability / 0.999) * 40)  # 40 points max
    error_score = max(0, (1 - (error_rate / 0.01)) * 30)  # 30 points max
    latency_score = max(0, min(30, (1 - (latency_p95_ms / 1000)) * 30))  # 30 points max

    total = round(avail_score + error_score + latency_score, 1)

    status = "healthy"
    if total < 60:
        status = "critical"
    elif total < 80:
        status = "degraded"

    return {
        "score": total,
        "status": status,
        "components": {
            "availability": round(avail_score, 1),
            "error_rate": round(error_score, 1),
            "latency": round(latency_score, 1),
        },
    }
