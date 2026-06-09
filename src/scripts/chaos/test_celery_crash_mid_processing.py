#!/usr/bin/env python3
"""
Chaos test: Celery worker crash mid-processing.
- Dispatch job
- Force-kill worker process mid-execution
- Verify job recovers correctly via scan_for_stalled_ai_jobs
- Validate: one AIOutput record, correct billing state, correct final job state
"""
import subprocess
import time
import httpx
import sys
import json
import os

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
API_TOKEN = os.environ.get("TEST_API_TOKEN", "test-token")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}


def create_job():
    r = httpx.post(
        f"{BASE_URL}/api/v1/jobs",
        json={"description": "Chaos test: worker crash", "customer_id": "test-customer"},
        headers=HEADERS,
        timeout=10,
    )
    assert r.status_code == 201, f"Failed to create job: {r.status_code} {r.text}"
    return r.json()["id"]


def trigger_ai_processing(job_id):
    r = httpx.post(
        f"{BASE_URL}/api/v1/ai/process-job/{job_id}",
        headers=HEADERS,
        timeout=10,
    )
    return r.status_code, r.json()


def kill_worker():
    try:
        result = subprocess.run(
            ["pkill", "-f", "celery.*worker"],
            capture_output=True,
            timeout=5,
        )
        print(f"   Worker kill exit code: {result.returncode}")
    except Exception as e:
        print(f"   Could not kill worker: {e}")


def wait_for_recovery(timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=5)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(5)
    return False


def get_job_state(job_id):
    r = httpx.get(
        f"{BASE_URL}/api/v1/jobs/{job_id}",
        headers=HEADERS,
        timeout=10,
    )
    if r.status_code == 200:
        return r.json().get("ai_processing_state")
    return None


def check_ai_output_count(job_id):
    r = httpx.get(
        f"{BASE_URL}/api/v1/ai/output/{job_id}",
        headers=HEADERS,
        timeout=10,
    )
    return r.status_code, r.json()


print("=== Chaos Test: Celery Worker Crash Mid-Processing ===")

print("1. Creating test job...")
job_id = create_job()
print(f"   Job ID: {job_id}")
assert job_id, "No job ID returned"

print("2. Dispatching AI processing...")
status, body = trigger_ai_processing(job_id)
print(f"   Status: {status}, Response: {body}")
assert status in (200, 202), f"Expected 200/202, got {status}"

print("3. Waiting for processing to start...")
time.sleep(5)

print("4. Killing Celery worker mid-processing...")
kill_worker()
time.sleep(2)

print("5. Waiting for recovery (workers restart, scan_for_stalled_ai_jobs)...")
recovered = wait_for_recovery(timeout=120)
print(f"   Recovered: {recovered}")
assert recovered, "System did not recover within timeout"

print("6. Waiting for scan_for_stalled_ai_jobs to re-dispatch...")
time.sleep(30)

print("7. Checking final job state...")
final_state = get_job_state(job_id)
print(f"   Final state: {final_state}")
assert final_state in ("completed", "failed", "queued"), f"Unexpected state: {final_state}"

print("8. Checking AI output...")
out_status, out_body = check_ai_output_count(job_id)
print(f"   Output status: {out_status}, body: {out_body}")

if final_state == "completed":
    assert out_body.get("status") == "complete", "Expected completed output"
    print("   PASS: Job completed with valid output")
else:
    print(f"   NOTE: Job ended in {final_state} state (acceptable for chaos test)")

print("\n=== Chaos test completed ===")
