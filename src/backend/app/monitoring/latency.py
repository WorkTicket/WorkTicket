"""Latency tracking middleware and performance SLI collection.

Provides per-endpoint latency histograms and SLO tracking for
availability and latency targets.

Configuration via environment:
    PERF_TRACKING_ENABLED: Enable latency tracking (default: true)
    LATENCY_SLO_MS: Target P95 latency in ms (default: 500)
    AVAILABILITY_SLO: Target availability fraction (default: 0.999)

Usage:
    In main.py, the middleware is added automatically. Endpoints can
    import track_latency for manual instrumentation.
"""

import asyncio
import logging
import os
import time
from collections import defaultdict

from fastapi import Request, Response

logger = logging.getLogger(__name__)

_PERF_TRACKING_ENABLED = os.environ.get("PERF_TRACKING_ENABLED", "true").lower() in ("true", "1", "yes")
_LATENCY_SLO_MS = float(os.environ.get("LATENCY_SLO_MS", "500"))
_AVAILABILITY_SLO = float(os.environ.get("AVAILABILITY_SLO", "0.999"))

# Aggregated metrics (per-endpoint)
_endpoint_latencies: dict[str, list[float]] = defaultdict(list)
_endpoint_errors: dict[str, int] = defaultdict(int)
_endpoint_requests: dict[str, int] = defaultdict(int)
_metrics_lock = asyncio.Lock()

# Max samples per endpoint (rolling window)
_MAX_SAMPLES = 10_000


def _normalize_path(path: str) -> str:
    """Remove variable path segments (UUIDs, etc.) for aggregation."""
    import re

    # Replace UUIDs with {id}
    path = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "{id}",
        path,
        flags=re.IGNORECASE,
    )
    # Replace numeric IDs
    path = re.sub(r"/\d+/", "/{id}/", path)
    return path


async def latency_middleware(request: Request, call_next) -> Response:
    """Track per-endpoint latency and error rate for SLO monitoring.

    Collects P50, P95, P99 latency histograms and availability metrics
    for each normalized endpoint path.
    """
    if not _PERF_TRACKING_ENABLED:
        return await call_next(request)

    start = time.monotonic()
    response = None
    is_error = False

    try:
        response = await call_next(request)
        is_error = response.status_code >= 500
    except Exception:
        is_error = True
        raise
    finally:
        elapsed_ms = (time.monotonic() - start) * 1000
        path = _normalize_path(request.url.path)
        method = request.method
        endpoint_key = f"{method}:{path}"

        async with _metrics_lock:
            _endpoint_requests[endpoint_key] += 1
            if is_error:
                _endpoint_errors[endpoint_key] += 1

            latencies = _endpoint_latencies[endpoint_key]
            latencies.append(elapsed_ms)
            if len(latencies) > _MAX_SAMPLES:
                # Keep only most recent samples
                _endpoint_latencies[endpoint_key] = latencies[-_MAX_SAMPLES:]

    return response


def get_percentile(sorted_values: list[float], percentile: float) -> float:
    """Calculate percentile from sorted values."""
    if not sorted_values:
        return 0.0
    index = int(len(sorted_values) * percentile / 100.0)
    index = min(index, len(sorted_values) - 1)
    index = max(index, 0)
    return sorted_values[index]


def get_latency_stats(endpoint_key: str | None = None) -> dict:
    """Get latency statistics for an endpoint or all endpoints.

    Returns:
        Dict with p50, p95, p99, avg, max, min, count, slo_violation
    """
    from copy import deepcopy

    samples = []
    if endpoint_key:
        samples = sorted(deepcopy(_endpoint_latencies.get(endpoint_key, [])))
    else:
        all_samples = []
        for v in _endpoint_latencies.values():
            all_samples.extend(v)
        samples = sorted(all_samples)

    if not samples:
        return {"p50": 0, "p95": 0, "p99": 0, "avg": 0, "max": 0, "min": 0, "count": 0, "slo_violation_pct": 0}

    p95 = get_percentile(samples, 95)
    violation_count = sum(1 for s in samples if s > _LATENCY_SLO_MS)

    return {
        "p50": round(get_percentile(samples, 50), 2),
        "p95": round(p95, 2),
        "p99": round(get_percentile(samples, 99), 2),
        "avg": round(sum(samples) / len(samples), 2),
        "max": round(max(samples), 2),
        "min": round(min(samples), 2),
        "count": len(samples),
        "slo_target_ms": _LATENCY_SLO_MS,
        "slo_violation_pct": round(violation_count / len(samples) * 100, 2) if samples else 0,
    }


def get_availability_stats(endpoint_key: str | None = None) -> dict:
    """Get availability statistics for an endpoint or all endpoints."""
    if endpoint_key:
        total = _endpoint_requests.get(endpoint_key, 0)
        errors = _endpoint_errors.get(endpoint_key, 0)
    else:
        total = sum(_endpoint_requests.values())
        errors = sum(_endpoint_errors.values())

    if total == 0:
        return {"total": 0, "errors": 0, "availability": 1.0, "slo_target": _AVAILABILITY_SLO, "slo_met": True}

    availability = (total - errors) / total
    return {
        "total": total,
        "errors": errors,
        "availability": round(availability, 6),
        "slo_target": _AVAILABILITY_SLO,
        "slo_met": availability >= _AVAILABILITY_SLO,
    }


def get_slo_summary() -> dict:
    """Get overall SLO summary for all tracked endpoints."""
    latency_stats = get_latency_stats()
    availability_stats = get_availability_stats()

    return {
        "latency": latency_stats,
        "availability": availability_stats,
        "endpoints_tracked": len(_endpoint_requests),
        "config": {
            "latency_slo_ms": _LATENCY_SLO_MS,
            "availability_slo": _AVAILABILITY_SLO,
        },
    }


def get_endpoint_slo_details() -> dict:
    """Get per-endpoint SLO details."""
    details = {}
    for endpoint_key in _endpoint_requests:
        details[endpoint_key] = {
            "latency": get_latency_stats(endpoint_key),
            "availability": get_availability_stats(endpoint_key),
        }
    return details
