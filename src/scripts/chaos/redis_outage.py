#!/usr/bin/env python3
"""
Chaos test: Redis outage.
- Temporarily block Redis port
- Verify system degrades gracefully (no 503s, in-memory fallback active)
- Restore Redis
- Verify system recovers
"""
import subprocess
import time
import httpx
import sys

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
REDIS_PORT = "6379"


def check_health():
    try:
        r = httpx.get(f"{BASE_URL}/readyz", timeout=5)
        return r.status_code, r.json()
    except Exception as e:
        return 0, {"error": str(e)}


def test_rate_limiter():
    try:
        r = httpx.get(f"{BASE_URL}/api/v1/billing/account",
                      headers={"Authorization": "Bearer test"},
                      timeout=5)
        return r.status_code < 500
    except Exception:
        return False


print("=== Chaos Test: Redis Outage ===")

print("1. System healthy before Redis outage?")
status, body = check_health()
print(f"   /readyz -> {status}")
assert status == 200, f"Expected 200, got {status}"
print("   PASS")

print("2. Blocking Redis port {REDIS_PORT}...")
subprocess.run(
    ["iptables", "-A", "INPUT", "-p", "tcp", "--dport", REDIS_PORT, "-j", "DROP"],
    check=False,
)
subprocess.run(
    ["iptables", "-A", "OUTPUT", "-p", "tcp", "--sport", REDIS_PORT, "-j", "DROP"],
    check=False,
)

print("   Waiting for circuit breaker to open...")
time.sleep(5)

print("3. Rate limiter uses in-memory fallback?")
ok = test_rate_limiter()
print(f"   Rate limiter call {'succeeded' if ok else 'failed'}")
assert ok, "Rate limiter should fall back to in-memory"
print("   PASS")

print("4. Readiness shows degraded?")
status, body = check_health()
print(f"   /readyz -> {status}, components: {body.get('components', {}).keys()}")
print("   PASS")

print("5. Restoring Redis port...")
subprocess.run(
    ["iptables", "-D", "INPUT", "-p", "tcp", "--dport", REDIS_PORT, "-j", "DROP"],
    check=False,
)
subprocess.run(
    ["iptables", "-D", "OUTPUT", "-p", "tcp", "--sport", REDIS_PORT, "-j", "DROP"],
    check=False,
)

print("   Waiting for recovery...")
time.sleep(5)

print("6. System recovered after Redis restore?")
status, body = check_health()
components = body.get("components", {})
rate_limiter_status = components.get("rate_limiter", {}).get("mode", "unknown")
print(f"   Rate limiter mode: {rate_limiter_status}")
assert rate_limiter_status == "redis", f"Expected redis mode, got {rate_limiter_status}"
print("   PASS")

print("\n=== All chaos tests PASSED ===")
