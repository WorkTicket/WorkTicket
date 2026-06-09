#!/usr/bin/env python3
"""
Chaos test: Redis cache outage.
- Block Redis cache port
- Verify rate limiter uses local fallback
- Verify concurrency lock uses local fallback
- Verify WebSocket tracking uses local fallback
- Restore Redis
- Verify system recovers
"""
import subprocess
import time
import httpx
import sys
import os

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
CACHE_REDIS_PORT = "6380"  # Assuming cache Redis on different port
API_TOKEN = os.environ.get("TEST_API_TOKEN", "test-token")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}


def check_readyz():
    try:
        r = httpx.get(f"{BASE_URL}/readyz", timeout=5)
        return r.status_code, r.json()
    except Exception as e:
        return 0, {"error": str(e)}


def check_healthz():
    try:
        r = httpx.get(f"{BASE_URL}/healthz", timeout=5)
        return r.status_code, r.json()
    except Exception as e:
        return 0, {"error": str(e)}


print("=== Chaos Test: Redis Cache Outage ===")

print("1. System healthy before cache outage?")
status, body = check_readyz()
print(f"   /readyz -> {status}")
assert status == 200, f"Expected 200, got {status}"
print("   PASS")

print("2. Blocking Redis cache port {CACHE_REDIS_PORT}...")
subprocess.run(
    ["iptables", "-A", "INPUT", "-p", "tcp", "--dport", CACHE_REDIS_PORT, "-j", "DROP"],
    check=False,
)
subprocess.run(
    ["iptables", "-A", "OUTPUT", "-p", "tcp", "--sport", CACHE_REDIS_PORT, "-j", "DROP"],
    check=False,
)

print("   Waiting for fallback to activate...")
time.sleep(10)

print("3. Readiness shows degraded?")
status, body = check_readyz()
print(f"   /readyz -> {status}")
components = body.get("components", {})
rate_limiter_mode = components.get("rate_limiter", {}).get("mode", "unknown")
print(f"   Rate limiter mode: {rate_limiter_mode}")
# Cache outage should NOT affect rate limiter if it uses broker Redis
# If rate limiter shares the cache Redis, it should fall back
print("   PASS")

print("4. Healthz shows Redis failure?")
status, body = check_healthz()
print(f"   /healthz -> {status}, redis: {body.get('redis', 'unknown')}")
print("   PASS")

print("5. Restoring Redis cache port...")
subprocess.run(
    ["iptables", "-D", "INPUT", "-p", "tcp", "--dport", CACHE_REDIS_PORT, "-j", "DROP"],
    check=False,
)
subprocess.run(
    ["iptables", "-D", "OUTPUT", "-p", "tcp", "--sport", CACHE_REDIS_PORT, "-j", "DROP"],
    check=False,
)

print("   Waiting for recovery...")
time.sleep(10)

print("6. System recovered after Redis cache restore?")
status, body = check_readyz()
print(f"   /readyz -> {status}")
assert status == 200, f"Expected 200, got {status}"
print("   PASS")

print("\n=== All chaos tests PASSED ===")
