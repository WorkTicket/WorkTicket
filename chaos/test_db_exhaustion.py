"""Chaos: DB pool exhaustion (K4)."""
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

async def slow_query(client):
    try:
        r = await client.get(f"{BASE}/healthz", timeout=30)
        return r.status_code
    except Exception:
        return 503

async def test():
    if not await _server_available():
        print("SKIP: Server not available at localhost:8000")
        return

    async with httpx.AsyncClient(timeout=30) as client:
        start = time.monotonic()
        results = await asyncio.gather(*[slow_query(client) for _ in range(100)])
        elapsed = time.monotonic() - start

        error_rate = sum(1 for s in results if s != 200) / len(results)
        print(f"Error rate under load: {error_rate:.0%} ({elapsed:.1f}s)")

        await asyncio.sleep(2)
        try:
            metrics = await client.get("http://localhost:8000/metrics")
        except Exception:
            pass

        assert error_rate < 0.5, f"Error rate too high: {error_rate:.0%}"
        print("K4 PASSED")

if __name__ == "__main__":
    asyncio.run(test())
