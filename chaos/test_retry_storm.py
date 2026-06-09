"""Chaos: Retry storm without deadlock (K1)."""
import asyncio
import httpx
import time

BASE = "http://localhost:8000/api/v1"

async def _server_available():
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{BASE}/healthz")
            return r.status_code == 200
    except Exception:
        return False

async def create_failing_job(client):
    payload = {"description": "", "media_type": "text"}
    r = await client.post(f"{BASE}/ai/process", json=payload)
    return r.status_code, r.elapsed.total_seconds()

async def test():
    if not await _server_available():
        print("SKIP: Server not available at localhost:8000")
        return

    async with httpx.AsyncClient(timeout=30) as client:
        started = time.monotonic()
        results = await asyncio.gather(*[create_failing_job(client) for _ in range(20)])
        elapsed = time.monotonic() - started

        health = await client.get(f"{BASE}/healthz")

        statuses = [s for s, _ in results]
        times = [t for _, t in results]

        print(f"Elapsed: {elapsed:.1f}s")
        print(f"Statuses: {statuses}")
        print(f"Max time: {max(times):.1f}s")
        print(f"Health: {health.status_code}")

        assert elapsed < 300, f"Took {elapsed:.1f}s — possible deadlock"
        assert health.status_code == 200, "Worker unresponsive during storm"
        assert all(s in (200, 202, 429) for s in statuses), f"Unexpected statuses: {statuses}"
        print("K1 PASSED")

if __name__ == "__main__":
    asyncio.run(test())
