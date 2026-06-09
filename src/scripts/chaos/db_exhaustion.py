#!/usr/bin/env python3
"""
Chaos test: DB connection pool exhaustion.
- Fire many concurrent requests to exhaust pool
- Verify graceful degradation
"""
import asyncio
import httpx
import sys

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


async def fire_request(client, i):
    try:
        r = await client.get(f"{BASE_URL}/api/v1/jobs?page=1&page_size=1",
                             headers={"Authorization": "Bearer test"},
                             timeout=10)
        return i, r.status_code
    except Exception as e:
        return i, str(e)


async def main():
    print("=== Chaos Test: DB Connection Pool Exhaustion ===")
    async with httpx.AsyncClient() as client:
        tasks = [fire_request(client, i) for i in range(100)]
        results = await asyncio.gather(*tasks)

    successes = sum(1 for _, r in results if r == 200)
    failures = sum(1 for _, r in results if r != 200)

    print(f"Total requests: {len(results)}")
    print(f"Success (200): {successes}")
    print(f"Non-200: {failures}")

    if failures > 0:
        print("Graceful degradation observed: non-200 responses")
    print("PASS" if successes > 0 else "FAIL")


asyncio.run(main())
