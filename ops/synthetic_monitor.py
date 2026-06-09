"""Synthetic end-to-end monitoring probe for job lifecycle.

Creates a test job via the API and verifies it reaches a terminal state.
Reports results via Prometheus push gateway and/or stdout.

Usage:
    python ops/synthetic_monitor.py

Required env vars:
    BASE_URL     - API base URL (default: http://localhost:8000)
    API_KEY      - API key or auth token for a test user
    PROMETHEUS_PUSH_GATEWAY - optional, for metric pushing

Metrics exported:
    synthetic_job_creation_duration_ms  (gauge, labels: status)
    synthetic_job_completion_duration_ms (gauge, labels: status)
    synthetic_job_success_total         (counter)
    synthetic_job_failure_total         (counter, labels: reason)
    synthetic_api_health                (gauge, labels: endpoint)
"""

import os
import sys
import time
import json
import uuid
import logging
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("synthetic_monitor")

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")
PUSH_GATEWAY = os.getenv("PROMETHEUS_PUSH_GATEWAY", "")

REQUEST_TIMEOUT = 10.0
JOB_TIMEOUT = 300.0
POLL_INTERVAL = 5.0

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}" if API_KEY else "",
    "User-Agent": "workticket-synthetic-monitor/1.0",
}

# --- HTTP helpers ---

try:
    import httpx
except ImportError:
    logger.error("httpx is required. Install with: pip install httpx")
    sys.exit(1)


def _request(method, path, json_body=None):
    url = urljoin(BASE_URL.rstrip("/") + "/", path.lstrip("/"))
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.request(method, url, headers=HEADERS, json=json_body)
            return resp.status_code, resp.json() if resp.text else {}
    except httpx.TimeoutException:
        logger.error("Request timeout: %s %s", method, url)
        return 504, {"error": "timeout"}
    except httpx.RequestError as e:
        logger.error("Request failed: %s %s — %s", method, url, e)
        return 502, {"error": str(e)}


# --- Probe steps ---


def check_health():
    """Check /healthz and /readyz endpoints."""
    results = {}
    for endpoint in ["/healthz", "/readyz", "/livez"]:
        status, body = _request("GET", endpoint)
        results[endpoint] = 1 if status == 200 else 0
        if status != 200:
            logger.warning("Health check %s returned %d", endpoint, status)
    return results


def run_job_lifecycle():
    """Create a job, poll until terminal state, verify completion."""
    start = time.monotonic()

    # 1. Create job
    _trade_type = os.getenv("SYNTHETIC_TRADE_TYPE", "hvac")
    job_payload = {
        "description": f"Synthetic probe job {uuid.uuid4().hex[:8]}",
        "trade_type": _trade_type,
    }
    status, body = _request("POST", "/api/v1/jobs", job_payload)
    creation_ms = (time.monotonic() - start) * 1000

    if status not in (200, 201):
        logger.error("Job creation failed: HTTP %d — %s", status, body)
        return {
            "success": False,
            "reason": f"create_failed_{status}",
            "creation_ms": creation_ms,
            "completion_ms": 0,
        }

    job_id = body.get("data", body).get("id", body.get("job_id", ""))
    if not job_id:
        logger.error("No job ID in creation response: %s", body)
        return {
            "success": False,
            "reason": "no_job_id",
            "creation_ms": creation_ms,
            "completion_ms": 0,
        }

    logger.info("Created synthetic job %s (%.0fms)", job_id, creation_ms)

    # 2. Poll until terminal state or timeout
    terminal_states = {"completed", "failed", "cancelled"}
    deadline = time.monotonic() + JOB_TIMEOUT

    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL)
        status, body = _request("GET", f"/api/v1/jobs/{job_id}")

        if status == 200:
            job_data = body.get("data", body)
            job_state = (
                job_data.get("ai_processing_state")
                or job_data.get("status")
                or ""
            ).lower()
            if job_state in terminal_states:
                completion_ms = (time.monotonic() - start) * 1000
                is_success = job_state == "completed"
                logger.info(
                    "Job %s reached terminal state '%s' (%.0fms)",
                    job_id, job_state, completion_ms,
                )
                return {
                    "success": is_success,
                    "reason": f"state_{job_state}" if not is_success else "",
                    "creation_ms": creation_ms,
                    "completion_ms": completion_ms,
                }

    # Timeout — job never reached terminal state
    completion_ms = (time.monotonic() - start) * 1000
    logger.error("Job %s did not reach terminal state within %.0fs", job_id, JOB_TIMEOUT)
    return {
        "success": False,
        "reason": "timeout",
        "creation_ms": creation_ms,
        "completion_ms": completion_ms,
    }


# --- Prometheus push ---


def push_metrics(health_results, job_result):
    """Push metrics to Prometheus push gateway."""
    if not PUSH_GATEWAY:
        return

    lines = [
        "# HELP synthetic_api_health Per-endpoint health (1=ok, 0=failed)",
        "# TYPE synthetic_api_health gauge",
    ]
    for endpoint, ok in health_results.items():
        safe_endpoint = endpoint.replace("/", "_").lstrip("_")
        lines.append(f'synthetic_api_health{{endpoint="{safe_endpoint}"}} {ok}')

    lines.extend([
        "",
        "# HELP synthetic_job_creation_duration_ms Time to create a job",
        "# TYPE synthetic_job_creation_duration_ms gauge",
        f'synthetic_job_creation_duration_ms{{status="{"ok" if job_result["success"] else job_result["reason"]}"}} {job_result["creation_ms"]:.0f}',
        "",
        "# HELP synthetic_job_completion_duration_ms Time from creation to terminal state",
        "# TYPE synthetic_job_completion_duration_ms gauge",
        f'synthetic_job_completion_duration_ms{{status="{"ok" if job_result["success"] else job_result["reason"]}"}} {job_result["completion_ms"]:.0f}',
        "",
        "# HELP synthetic_job_success_total Total successful probe cycles",
        "# TYPE synthetic_job_success_total counter",
        f'synthetic_job_success_total {1 if job_result["success"] else 0}',
        "",
        "# HELP synthetic_job_failure_total Total failed probe cycles",
        "# TYPE synthetic_job_failure_total counter",
        f'synthetic_job_failure_total{{reason="{job_result["reason"]}"}} {0 if job_result["success"] else 1}',
    ])

    payload = "\n".join(lines)
    job_name = "workticket_synthetic_monitor"
    push_url = f"{PUSH_GATEWAY.rstrip('/')}/metrics/job/{job_name}"

    try:
        with httpx.Client(timeout=5) as client:
            resp = client.put(push_url, content=payload)
            if resp.status_code not in (200, 202):
                logger.warning("Push gateway returned %d", resp.status_code)
    except Exception as e:
        logger.warning("Failed to push metrics: %s", e)


# --- Main ---


def main():
    logger.info("Starting synthetic monitor probe — %s", BASE_URL)

    health_results = check_health()
    job_result = run_job_lifecycle()

    push_metrics(health_results, job_result)

    # Exit with code for systemd/CronJob reporting
    all_healthy = all(v == 1 for v in health_results.values())
    if not all_healthy:
        logger.error("Health checks failed: %s", health_results)
    if not job_result["success"]:
        logger.error("Job lifecycle failed: %s", job_result["reason"])

    all_ok = all_healthy and job_result["success"]
    logger.info(
        "Probe %s — health=%s job=%s (creation=%.0fms completion=%.0fms)",
        "PASS" if all_ok else "FAIL",
        "ok" if all_healthy else "degraded",
        "ok" if job_result["success"] else job_result["reason"],
        job_result["creation_ms"],
        job_result["completion_ms"],
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
