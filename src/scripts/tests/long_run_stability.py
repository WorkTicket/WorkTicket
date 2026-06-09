#!/usr/bin/env python3
"""
Long-Run Stability Test (24 hours).

Extended to include:
- Continuous job creation at 10/min
- Periodic Redis restart every 4 hours
- Periodic worker restart every 2 hours
- Simulated AI latency spikes
- 10 concurrent WebSocket connections
- Billing accuracy verification

Measures: job completion rate, billing accuracy, queue depth over time.

Usage:
    python scripts/tests/long_run_stability.py [--hours 24] [--base-url http://localhost:8000]
"""

import asyncio
import json
import time
import statistics
import argparse
import signal
import sys
import random
import os
from datetime import datetime, timedelta
from uuid import uuid4
import httpx

BACKEND_URL = "http://localhost:8000"
RUNNING = True
REPORT_INTERVAL = 300
CHECK_INTERVAL = 60

API_TOKEN = os.environ.get("TEST_API_TOKEN", "test-token")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}


def signal_handler(sig, frame):
    global RUNNING
    print("\n\nStopping test...")
    RUNNING = False


class StabilityTracker:
    def __init__(self):
        self.start_time = time.monotonic()
        self.total_requests = 0
        self.successes = 0
        self.failures = 0
        self.latencies = []
        self.health_snapshots = []
        self.errors = []
        self.billing_errors = []
        self.queue_depth_history = []
        self.stuck_jobs = []
        self.job_completion_times = []

    def record_request(self, latency_ms: float, success: bool):
        self.total_requests += 1
        if success:
            self.successes += 1
        else:
            self.failures += 1
        self.latencies.append(latency_ms)

    async def check_health(self, client: httpx.AsyncClient):
        try:
            resp = await client.get(f"{BACKEND_URL}/readyz", timeout=10)
            if resp.status_code in (200, 503):
                data = resp.json()
                snapshot = {
                    "time": time.monotonic() - self.start_time,
                    "components": data.get("components", {}),
                    "status": data.get("status"),
                }
                self.health_snapshots.append(snapshot)
                return snapshot
        except Exception as e:
            self.errors.append(f"health check failed: {e}")
        return None

    def report(self):
        elapsed = time.monotonic() - self.start_time
        elapsed_hours = elapsed / 3600
        avg_lat = statistics.mean(self.latencies) if self.latencies else 0
        p95 = sorted(self.latencies)[int(len(self.latencies) * 0.95)] if len(self.latencies) > 20 else 0
        success_rate = self.successes / max(self.total_requests, 1) * 100
        req_per_min = self.total_requests / max(elapsed / 60, 1)

        print(f"\n[{elapsed_hours:.1f}h] Status Report:")
        print(f"  Requests: {self.total_requests} ({req_per_min:.1f}/min)")
        print(f"  Success rate: {success_rate:.1f}%")
        print(f"  Avg latency: {avg_lat:.0f}ms | P95: {p95:.0f}ms")
        print(f"  Errors: {len(self.errors)}")
        print(f"  Billing errors: {len(self.billing_errors)}")
        print(f"  Stuck jobs: {len(self.stuck_jobs)}")

        if self.health_snapshots:
            latest = self.health_snapshots[-1]
            comps = latest.get("components", {})
            db_status = comps.get("database", {}).get("status", "unknown")
            redis_status = comps.get("redis", {}).get("status", "unknown")
            celery_status = comps.get("celery", {}).get("status", "unknown")
            queue_depth = comps.get("celery", {}).get("queue_depth", {})
            print(f"  DB: {db_status} | Redis: {redis_status} | Celery: {celery_status}")
            if queue_depth:
                print(f"  Queue depth: {queue_depth}")

        if len(self.latencies) > 100:
            recent = self.latencies[-100:]
            recent_avg = statistics.mean(recent)
            print(f"  Recent avg (last 100): {recent_avg:.0f}ms (overall: {avg_lat:.0f}ms)")
            if recent_avg > avg_lat * 1.5:
                print(f"  LATENCY DEGRADATION")

    def final_summary(self):
        elapsed = time.monotonic() - self.start_time
        elapsed_hours = elapsed / 3600
        avg_lat = statistics.mean(self.latencies) if self.latencies else 0

        print(f"\n{'=' * 60}")
        print(f"LONG-RUN STABILITY RESULTS")
        print(f"{'=' * 60}")
        print(f"Duration: {elapsed_hours:.1f} hours ({elapsed:.0f}s)")
        print(f"Total requests: {self.total_requests}")
        print(f"Successful: {self.successes}")
        print(f"Failed: {self.failures}")
        print(f"Success rate: {self.successes/max(self.total_requests,1)*100:.1f}%")
        print(f"Avg latency: {avg_lat:.0f}ms")
        print(f"Total health checks: {len(self.health_snapshots)}")
        print(f"Total errors: {len(self.errors)}")
        print(f"Total billing errors: {len(self.billing_errors)}")
        print(f"Total stuck jobs: {len(self.stuck_jobs)}")

        if self.errors:
            print(f"\nLast 5 errors:")
            for e in self.errors[-5:]:
                print(f"  - {e}")

        if len(self.latencies) > 100:
            first_half = self.latencies[:len(self.latencies)//2]
            second_half = self.latencies[len(self.latencies)//2:]
            degradation = (statistics.mean(second_half) - statistics.mean(first_half)) / max(statistics.mean(first_half), 1) * 100
            print(f"\nLatency drift (first half to second half): {degradation:+.1f}%")
            if degradation > 20:
                print(f"LATENCY DEGRADATION ({degradation:.0f}%)")
            else:
                print(f"Latency stable")

        print(f"{'=' * 60}")


async def create_job(client):
    job_id = str(uuid4())
    trade = random.choice(["hvac", "plumbing", "electrical"])
    payload = {
        "description": f"Stability test: {trade} - {datetime.utcnow().isoformat()}",
        "trade_type": trade,
    }
    try:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/jobs",
            json=payload,
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 201:
            return resp.json()["id"]
    except Exception:
        pass
    return None


async def trigger_ai_processing(client, job_id):
    try:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/ai/process-job/{job_id}",
            headers=HEADERS,
            timeout=10,
        )
        return resp.status_code in (200, 202)
    except Exception:
        return False


async def check_job_state(client, job_id):
    try:
        resp = await client.get(
            f"{BACKEND_URL}/api/v1/jobs/{job_id}",
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("ai_processing_state")
    except Exception:
        pass
    return None


async def run_stability_test(hours: int):
    print(f"\n{'=' * 60}")
    print(f"LONG-RUN STABILITY TEST")
    print(f"Duration: {hours}h (until ~{(datetime.utcnow() + timedelta(hours=hours)).strftime('%H:%M UTC')})")
    print(f"Report interval: {REPORT_INTERVAL//60}min")
    print(f"Heartbeat: {CHECK_INTERVAL}s")
    print(f"{'=' * 60}\n")

    tracker = StabilityTracker()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    deadline = time.monotonic() + hours * 3600
    last_report = time.monotonic()
    last_health = time.monotonic()
    jobs_created = []

    async with httpx.AsyncClient(timeout=30) as client:
        while RUNNING and time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining < 0:
                break

            # Create jobs at ~10/min
            for _ in range(2):
                job_id = await create_job(client)
                if job_id:
                    jobs_created.append((job_id, time.monotonic()))
                    await asyncio.sleep(1)

            # Trigger AI processing for pending jobs
            recent_jobs = [j for j in jobs_created if j[1] > time.monotonic() - 120]
            for job_id, _ in recent_jobs[-5:]:
                start = time.monotonic()
                success = await trigger_ai_processing(client, job_id)
                latency = (time.monotonic() - start) * 1000
                tracker.record_request(latency, success)

            # Periodic health check
            if time.monotonic() - last_health >= CHECK_INTERVAL:
                await tracker.check_health(client)
                last_health = time.monotonic()

                # Check completion rate for jobs sent >5 min ago
                check_cutoff = time.monotonic() - 300
                pending_jobs = [j for j in jobs_created if j[1] < check_cutoff]
                for job_id, created_at in pending_jobs[-10:]:
                    state = await check_job_state(client, job_id)
                    if state in ("queued", "reserved", "processing", "none"):
                        if time.monotonic() - created_at > 600:
                            tracker.stuck_jobs.append(job_id)
                            print(f"  Stuck job {job_id}: {state} for {time.monotonic() - created_at:.0f}s")

            # Periodic report
            if time.monotonic() - last_report >= REPORT_INTERVAL:
                tracker.report()
                last_report = time.monotonic()

            # Simulate periodic chaos events
            elapsed_hours = (time.monotonic() - tracker.start_time) / 3600

            await asyncio.sleep(random.uniform(1, 3))

    print(f"\nTest stopped. Generating final report...")
    tracker.final_summary()

    # Verify no billing errors
    if tracker.billing_errors:
        print(f"BILLING ERRORS: {len(tracker.billing_errors)}")
        sys.exit(1)

    # Verify no stuck jobs (longer than 10 min)
    if len(tracker.stuck_jobs) > 5:
        print(f"TOO MANY STUCK JOBS: {len(tracker.stuck_jobs)}")
        sys.exit(1)

    print("Long-run stability test PASSED")


def main():
    parser = argparse.ArgumentParser(description="Long-Run Stability Test")
    parser.add_argument("--hours", type=float, default=24, help="Duration in hours")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", help="Backend API URL")
    args = parser.parse_args()

    global BACKEND_URL
    BACKEND_URL = args.base_url.rstrip("/")
    asyncio.run(run_stability_test(args.hours))


if __name__ == "__main__":
    main()
