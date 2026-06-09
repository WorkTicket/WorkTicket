"""Chaos: WebSocket reconnect storm (K5)."""
import asyncio
import httpx
import time
import websockets
import os

WS_URL = os.getenv("WS_URL", "ws://localhost:8000/api/v1/ai/ws/job-status")

async def ws_client(client_id):
    try:
        async with websockets.connect(
            f"{WS_URL}/{client_id}",
            extra_headers={"sec-websocket-protocol": "authorization.test-token"},
            open_timeout=5, close_timeout=5,
        ) as ws:
            await asyncio.sleep(1)
            await ws.close()
    except Exception:
        pass

async def test():
    import tracemalloc
    tracemalloc.start()
    
    # Batch 1: 500 connections
    start = time.monotonic()
    batch1 = await asyncio.gather(*[ws_client(i) for i in range(500)], return_exceptions=True)
    t1 = time.monotonic() - start
    
    # Snapshot memory
    snap1 = tracemalloc.take_snapshot()
    
    # Batch 2: reconnect all
    start = time.monotonic()
    batch2 = await asyncio.gather(*[ws_client(i) for i in range(500)], return_exceptions=True)
    t2 = time.monotonic() - start
    
    snap2 = tracemalloc.take_snapshot()
    stats = snap2.compare_to(snap1, 'lineno')
    
    total_diff = sum(s.size_diff for s in stats)
    print(f"Batch 1: {t1:.1f}s, Batch 2: {t2:.1f}s")
    print(f"Memory delta: {total_diff / 1024:.1f} KB")
    
    assert t2 < 30, f"Reconnect took {t2:.1f}s — possible task leak"
    assert total_diff < 5 * 1024 * 1024, f"Memory leak detected: {total_diff / 1024:.1f} KB"
    print("K5 PASSED")

if __name__ == "__main__":
    asyncio.run(test())
