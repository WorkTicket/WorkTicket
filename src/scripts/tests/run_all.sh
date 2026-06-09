#!/bin/bash
# Run all stability and validation tests
set -e

BASE_URL="${1:-http://localhost:8000}"

echo "========================================"
echo "  WORKTICKET COMPLETE TEST SUITE"
echo "  Target: $BASE_URL"
echo "========================================"
echo ""

# ── Phase A: System Stability ──
echo "=== [A1] AI Load Stress Test ==="
python3 scripts/tests/stress_load.py --concurrent 50 --duration 30 --base-url "$BASE_URL"
echo ""

echo "=== [A2] Queue Backlog Flood Test ==="
python3 scripts/tests/queue_flood.py --jobs 200 --base-url "$BASE_URL"
echo ""

echo "=== [A3] Service Crash Recovery Test ==="
bash scripts/tests/service_crash.sh
echo ""

# ── Phase B: User Simulation ──
echo "=== [B1] Real User Simulation ==="
python3 scripts/tests/user_simulation.py --users 10 --duration 60 --base-url "$BASE_URL"
echo ""

# ── Phase C: Flow Validation ──
echo "=== [C1] End-to-End Flow Validation ==="
python3 scripts/tests/e2e_flow_test.py --base-url "$BASE_URL"
echo ""

# ── Phase D: Observability ──
echo "=== [D1] Metrics Check ==="
curl -sf "$BASE_URL/ai/metrics" | python3 -m json.tool
echo ""

echo "=== [D2] Business Metrics Check ==="
curl -sf "$BASE_URL/ai/metrics/business?minutes=1440" | python3 -m json.tool
echo ""

echo "=== [D3] Health Check ==="
curl -sf "$BASE_URL/health" | python3 -m json.tool
echo ""

# ── Summary ──
echo "========================================"
echo "  TEST SUITE COMPLETE"
echo ""
echo "  For long-run stability:"
echo "    python3 scripts/tests/long_run_stability.py --hours 12"
echo "========================================"
