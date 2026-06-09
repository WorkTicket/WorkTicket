#!/usr/bin/env python3
"""
AI Load Stress Test — 50-200 concurrent AI requests.

Usage:
    python scripts/tests/stress_load.py [--concurrent 50] [--base-url http://localhost:8000]

This test fires concurrent requests to the AI process-job endpoint
and measures throughput, failure rate, and circuit breaker behavior.
"""

import asyncio
import json
import time
import statistics
import argparse
from uuid import UUID, uuid4
import httpx

BACKEND_URL = "http://localhost:8000"


async def send_ai_request(client: httpx.AsyncClient, job_id: str, index: int):
    """Send one AI process request with mixed workload."""
    payload = {
        "description": f"Test job {index}: HVAC compressor not cooling, unusual noise from unit",
        "trade_type": "hvac" if index % 3 == 0 else ("plumbing" if index % 3 == 1 else "electrical"),
        "audio_url": f"https://example.com/audio/test_{index}.m4a" if index % 4 == 0 else None,
        "image_urls": [f"https://example.com/img/test_{index}.jpg"] if index % 2 == 0 else [],
    }
    start = time.monotonic()
    try:
        resp = await client.post(
            f"{BACKEND_URL}/ai/process-job/{job_id}",
            json=payload,
            timeout=30,
        )
        elapsed = (time.monotonic() - start) * 1000
        return {
            "index": index,
            "status": resp.status_code,
            "latency_ms": round(elapsed, 2),
            "body": resp.json() if resp.status_code < 500 else None,
            "error": None,
        }
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return {
            "index": index,
            "status": 0,
            "latency_ms": round(elapsed, 2),
            "body": None,
            "error": str(e),
        }


async def run_load_test(concurrent: int, duration_seconds: int = 30):
    print(f"\n{'='*60}")
    print(f"  AI LOAD STRESS TEST")
    print(f"  Concurrent requests: {concurrent}")
    print(f"  Duration: {duration_seconds}s")
    print(f"{'='*60}\n")

    results = []
    client = httpx.AsyncClient(timeout=30)
    try:
        deadline = time.monotonic() + duration_seconds
        batch = 0
        while time.monotonic() < deadline:
            tasks = []
            for i in range(concurrent):
                job_id = str(uuid4())
                tasks.append(send_ai_request(client, job_id, batch * concurrent + i))
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in batch_results:
                if isinstance(r, dict):
                    results.append(r)
            batch += 1
            print(f"  Batch {batch}: sent {concurrent} requests")
            await asyncio.sleep(1)
    finally:
        await client.aclose()

    if not results:
        print("  No results collected.")
        return

    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]
    successes = [r for r in results if r["status"] == 200]
    rate_limited = [r for r in results if r["status"] == 429]
    errors = [r for r in results if r["status"] == 0 or r["status"] >= 500]
    timeouts = [r for r in results if r["error"] and "timeout" in r["error"].lower()]

    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}")
    print(f"  Total requests:       {len(results)}")
    print(f"  Successful (200):     {len(successes)} ({len(successes)/len(results)*100:.1f}%)")
    print(f"  Rate limited (429):   {len(rate_limited)}")
    print(f"  Errors (5xx/0):       {len(errors)}")
    print(f"  Timeouts:             {len(timeouts)}")
    if latencies:
        print(f"\n  Latency (ms):")
        print(f"    Min:    {min(latencies):.1f}")
        print(f"    Max:    {max(latencies):.1f}")
        print(f"    Avg:    {statistics.mean(latencies):.1f}")
        print(f"    Median: {statistics.median(latencies):.1f}")
        if len(latencies) > 1:
            print(f"    P95:    {sorted(latencies)[int(len(latencies)*0.95)]:.1f}")
            print(f"    P99:    {sorted(latencies)[int(len(latencies)*0.99)]:.1f}")
    print(f"\n  Requests/sec: {len(results)/duration_seconds:.1f}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="AI Load Stress Test")
    parser.add_argument("--concurrent", type=int, default=50, help="Number of concurrent requests per batch")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", help="Backend API URL")
    args = parser.parse_args()

    global BACKEND_URL
    BACKEND_URL = args.base_url.rstrip("/")

    asyncio.run(run_load_test(args.concurrent, args.duration))


if __name__ == "__main__":
    main()
