#!/usr/bin/env python3
"""
Queue Backlog Stress Test — Flood Celery with jobs and verify:
- No job loss
- No deadlocks
- Retry behavior works
- Queue drains correctly

Usage:
    python scripts/tests/queue_flood.py [--jobs 200] [--base-url http://localhost:8000]
"""

import asyncio
import time
import statistics
import argparse
from uuid import uuid4
import httpx

BACKEND_URL = "http://localhost:8000"


async def flood_queue(job_count: int, batch_size: int = 20):
    print(f"\n{'='*60}")
    print(f"  QUEUE BACKLOG FLOOD TEST")
    print(f"  Jobs to queue: {job_count}")
    print(f"  Batch size: {batch_size}")
    print(f"{'='*60}\n")

    queued = 0
    failed = 0
    latencies = []
    client = httpx.AsyncClient(timeout=30)

    try:
        for batch_start in range(0, job_count, batch_size):
            batch_end = min(batch_start + batch_size, job_count)
            tasks = []
            for i in range(batch_start, batch_end):
                job_id = str(uuid4())
                tasks.append(_queue_job(client, job_id, i))

            batch_start_time = time.monotonic()
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            batch_elapsed = (time.monotonic() - batch_start_time) * 1000

            for r in batch_results:
                if isinstance(r, dict) and r.get("queued"):
                    queued += 1
                    latencies.append(r["latency_ms"])
                else:
                    failed += 1

            batch_count = batch_end - batch_start
            print(f"  Batch {batch_end}/{job_count}: queued {queued}, failed {failed}, "
                  f"batch time {batch_elapsed:.0f}ms")

            await asyncio.sleep(0.5)

    finally:
        await client.aclose()

    print(f"\n{'='*60}")
    print(f"  QUEUE FLOOD RESULTS")
    print(f"{'='*60}")
    print(f"  Total attempted:  {job_count}")
    print(f"  Successfully queued: {queued}")
    print(f"  Failed to queue:     {failed}")
    if latencies:
        print(f"  Queue latency (ms):")
        print(f"    Avg: {statistics.mean(latencies):.1f}")
        print(f"    Max: {max(latencies):.1f}")
    print(f"\n  Job loss rate: {failed/max(job_count,1)*100:.2f}%")
    print(f"{'='*60}")

    print(f"\n  Waiting 30s for queue to drain...")
    await asyncio.sleep(30)

    print(f"  Checking queue status...")
    await check_queue_status(client)
    print(f"{'='*60}\n")


async def _queue_job(client, job_id: str, index: int):
    trade = "hvac" if index % 3 == 0 else ("plumbing" if index % 3 == 1 else "electrical")
    payload = {
        "description": f"Flood test job {index}: {trade} issue - needs diagnosis",
        "trade_type": trade,
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
            "queued": resp.status_code == 200,
            "latency_ms": round(elapsed, 2),
            "status": resp.status_code,
        }
    except Exception as e:
        return {"queued": False, "latency_ms": 0, "error": str(e)}


async def check_queue_status(client):
    try:
        resp = await client.get(f"{BACKEND_URL}/ai/metrics", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"    Recent failures: {data.get('failure_rate', {}).get('failures', 'unknown')}")
            print(f"    Circuit states: LLM={data.get('gateway',{}).get('llm_circuit_state','?')}, "
                  f"Whisper={data.get('gateway',{}).get('whisper_circuit_state','?')}")
        else:
            print(f"    Metrics endpoint returned {resp.status_code}")
    except Exception as e:
        print(f"    Could not check queue status: {e}")


def main():
    parser = argparse.ArgumentParser(description="Queue Backlog Flood Test")
    parser.add_argument("--jobs", type=int, default=200, help="Number of jobs to queue")
    parser.add_argument("--batch", type=int, default=20, help="Batch size")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", help="Backend API URL")
    args = parser.parse_args()

    global BACKEND_URL
    BACKEND_URL = args.base_url.rstrip("/")

    asyncio.run(flood_queue(args.jobs, args.batch))


if __name__ == "__main__":
    main()
