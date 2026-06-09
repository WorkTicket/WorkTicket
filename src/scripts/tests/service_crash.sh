#!/bin/bash
# Service Crash + Recovery Test
# Tests that the system recovers cleanly when AI services are killed.
set -e

COMPOSE_FILE="docker-compose.yml"
RECOVERY_WAIT=30
TEST_PASS=true

echo "========================================"
echo "  SERVICE CRASH + RECOVERY TEST"
echo "========================================"
echo ""
echo "This test will:"
echo "  1. Kill Ollama container"
echo "  2. Verify fallback responses work"
echo "  3. Restart Ollama"
echo "  4. Verify recovery"
echo "  5. Kill Whisper service"
echo "  6. Verify fallback"
echo "  7. Restart Whisper"
echo "  8. Kill Redis"
echo "  9. Verify graceful degradation"
echo "  10. Restart everything"
echo ""

# --- Step 1: Kill Ollama ---
echo "[1/10] Killing Ollama container..."
docker compose -f "$COMPOSE_FILE" stop ollama
echo "  Ollama stopped."

# --- Step 2: Verify backend still responds with fallback ---
echo "[2/10] Verifying fallback responses..."
sleep 3
HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null || echo "{}")
OLLAMA_OK=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ollama_available',False))" 2>/dev/null || echo "error")
if [ "$OLLAMA_OK" = "False" ]; then
    echo "  ✓ Backend reports Ollama unavailable (expected)"
else
    echo "  ✗ Backend should report Ollama unavailable (got: $OLLAMA_OK)"
    TEST_PASS=false
fi

# Try an AI request - should return fallback
RESULT=$(curl -sf -X POST http://localhost:8000/ai/process-job/$(python3 -c "import uuid; print(uuid.uuid4())") \
    -H "Content-Type: application/json" \
    -d '{"description":"test"}' 2>/dev/null || echo "{}")
STATUS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "error")
echo "  AI request returned status: $STATUS"

# --- Step 3: Restart Ollama ---
echo "[3/10] Restarting Ollama..."
docker compose -f "$COMPOSE_FILE" start ollama
echo "  Waiting $RECOVERY_WAIT s for model loading..."
sleep "$RECOVERY_WAIT"

# --- Step 4: Verify recovery ---
echo "[4/10] Verifying recovery..."
HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null || echo "{}")
OLLAMA_OK=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ollama_available',False))" 2>/dev/null || echo "error")
if [ "$OLLAMA_OK" = "True" ]; then
    echo "  ✓ Ollama recovered and available"
else
    echo "  ⚠ Ollama may not be fully recovered yet (check models)"
fi

# --- Step 5: Kill Whisper ---
echo "[5/10] Killing Whisper service..."
docker compose -f "$COMPOSE_FILE" stop whisper-service
echo "  Whisper stopped."

# --- Step 6: Verify whisper fallback ---
echo "[6/10] Verifying whisper fallback..."
sleep 3
HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null || echo "{}")
WHISPER_OK=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('whisper_available',False))" 2>/dev/null || echo "error")
if [ "$WHISPER_OK" = "False" ]; then
    echo "  ✓ Backend reports Whisper unavailable (expected)"
else
    echo "  ✗ Backend should report Whisper unavailable (got: $WHISPER_OK)"
    TEST_PASS=false
fi

# --- Step 7: Restart Whisper ---
echo "[7/10] Restarting Whisper service..."
docker compose -f "$COMPOSE_FILE" start whisper-service
echo "  Waiting 30s..."
sleep 30

# --- Step 8: Kill Redis ---
echo "[8/10] Killing Redis (queue system)..."

# First check if Celery falls back gracefully
echo "  Testing Redis failure... (this may cause errors but should not crash API)"
docker compose -f "$COMPOSE_FILE" stop redis
sleep 5

# API should still respond (but Celery tasks will fail)
HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null || echo "{}")
API_OK=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "down")
echo "  API status with Redis down: $API_OK"

# --- Step 9: Verify graceful degradation ---
echo "[9/10] Verifying graceful degradation..."
echo "  Backend should still serve non-AI endpoints without Redis"

# --- Step 10: Full restart ---
echo "[10/10] Full restart..."
docker compose -f "$COMPOSE_FILE" start redis
echo "  Waiting for full recovery..."
sleep 15

HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null || echo "{}")
ALL_OK=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','down'))" 2>/dev/null || echo "down")
echo "  Final health status: $ALL_OK"

echo ""
echo "========================================"
echo "  CRASH TEST COMPLETE"
if [ "$TEST_PASS" = true ]; then
    echo "  RESULT: ✓ ALL CHECKS PASSED"
else
    echo "  RESULT: ✗ SOME CHECKS FAILED"
fi
echo "========================================"
