#!/bin/bash
set -euo pipefail

SECRET_NAME="${1:-}"
ENV_FILE="${2:-.env}"
GRACE_PERIOD="${ROTATION_GRACE_PERIOD:-300}"

generate_password() {
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
}

generate_hex_key() {
  python3 -c "import secrets; print(secrets.token_hex(32))"
}

# Runtime key rotation via Redis pub/sub for in-process key updates
notify_rotation() {
  local secret_name="$1"
  local grace="$2"
  echo "[rotation] Publishing rotation event for ${secret_name} (grace=${grace}s)"
  docker compose exec -T redis-broker redis-cli PUBLISH "secret:rotation" "{\"secret\":\"${secret_name}\",\"grace\":${grace},\"timestamp\":$(date +%s)}" 2>/dev/null || true
}

log_rotation() {
  local secret="$1"
  local new_hash
  new_hash=$(echo -n "$2" | sha256sum | cut -d' ' -f1 | cut -c1-16)
  echo "[$(date -Iseconds)] ROTATION_AUDIT secret=${secret} new_hash=${new_hash} grace=${GRACE_PERIOD}s" >> "${ENV_FILE}.rotation-audit.log"
}

# Auto-detect all rotatable secrets from .env file
detect_rotatable() {
  echo "Detecting rotatable secrets in ${ENV_FILE}..."
  grep -oP '^[A-Z_]+(?==)' "$ENV_FILE" 2>/dev/null | while read -r key; do
    case "$key" in
      POSTGRES_PASSWORD|REDIS_PASSWORD|SECRET_KEY|METRICS_ACCESS_TOKEN|\
      CELERY_TASK_SIGNING_KEY|PII_ENCRYPTION_KEY|PUSH_TOKEN_ENCRYPTION_KEY|\
      STRIPE_WEBHOOK_SECRET|CLERK_SECRET_KEY|RESEND_API_KEY|TWILIO_AUTH_TOKEN)
        echo "  - $key (rotatable)"
        ;;
    esac
  done
}

if [ -z "$SECRET_NAME" ]; then
  echo "Usage: $0 <secret-name> [env-file]"
  echo ""
  echo "Available secrets:"
  echo "  postgres_password     PostgreSQL database password"
  echo "  redis_password        Redis broker + cache password"
  echo "  secret_key            Application SECRET_KEY"
  echo "  stripe_webhook        Stripe webhook signing secret (manual: Stripe Dashboard)"
  echo "  metrics_token         Prometheus metrics access token"
  echo "  celery_signing_key    Celery task HMAC signing key"
  echo "  pii_encryption_key    PII field encryption key"
  echo "  push_token_key        Push notification token encryption key"
  echo "  all_auto              Auto-detect and rotate all supported secrets"
  echo "  detect                Show all rotatable secrets in env file"
  echo ""
  echo "Grace period: ${GRACE_PERIOD}s (set ROTATION_GRACE_PERIOD env var to override)"
  exit 1
fi

case "$SECRET_NAME" in
  detect|list)
    detect_rotatable
    exit 0
    ;;

  all_auto)
    echo "=== Auto-rotating all supported secrets ==="
    for secret in redis_password secret_key metrics_token celery_signing_key pii_encryption_key push_token_key; do
      echo ""
      echo "--- Rotating ${secret} ---"
      $0 "$secret" "$ENV_FILE" || echo "  [WARN] Rotation of ${secret} failed, continuing..."
      sleep 2
    done
    echo "=== Postgres password rotation must be done separately for safety ==="
    echo "Run: $0 postgres_password"
    exit 0
    ;;

  postgres_password)
    NEW_PASS=$(generate_password)
    ESCAPED_PASS="${NEW_PASS//\'/\'\'}"
    PGPASSWORD="$NEW_PASS" psql -h localhost -U postgres -c "ALTER ROLE postgres WITH PASSWORD '$ESCAPED_PASS';"
    sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$NEW_PASS|" "$ENV_FILE"
    log_rotation "postgres_password" "$NEW_PASS"
    echo "Rotated postgres_password. Restart: docker compose up -d backend celery-worker-* celery-beat pgbouncer"
    ;;

  redis_password)
    NEW_PASS=$(generate_password)
    OLD_PASS=$(grep REDIS_PASSWORD "$ENV_FILE" | cut -d= -f2)
    REDISCLI_AUTH="$OLD_PASS" docker compose exec -T redis-broker redis-cli CONFIG SET requirepass "$NEW_PASS"
    REDISCLI_AUTH="$OLD_PASS" docker compose exec -T redis-cache redis-cli CONFIG SET requirepass "$NEW_PASS"
    REDISCLI_AUTH="$OLD_PASS" docker compose exec -T redis-broker redis-cli CONFIG REWRITE 2>/dev/null || true
    REDISCLI_AUTH="$OLD_PASS" docker compose exec -T redis-cache redis-cli CONFIG REWRITE 2>/dev/null || true
    sed -i "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=$NEW_PASS|" "$ENV_FILE"
    log_rotation "redis_password" "$NEW_PASS"
    notify_rotation "redis_password" "$GRACE_PERIOD"
    echo "Rotated redis_password."
    ;;

  secret_key)
    NEW_KEY=$(generate_hex_key)
    sed -i "s|SECRET_KEY=.*|SECRET_KEY=$NEW_KEY|" "$ENV_FILE"
    log_rotation "secret_key" "$NEW_KEY"
    echo "Rotated SECRET_KEY. Restart backend to pick up new key."
    ;;

  stripe_webhook)
    echo "Manual: Stripe Dashboard -> Developers -> Webhooks -> Roll signing secret"
    echo "After rolling in Stripe, update STRIPE_WEBHOOK_SECRET in ${ENV_FILE}"
    ;;

  metrics_token)
    NEW_TOKEN=$(generate_password)
    sed -i "s|METRICS_ACCESS_TOKEN=.*|METRICS_ACCESS_TOKEN=$NEW_TOKEN|" "$ENV_FILE"
    log_rotation "metrics_token" "$NEW_TOKEN"
    echo "Rotated METRICS_ACCESS_TOKEN."
    ;;

  celery_signing_key)
    NEW_KEY=$(generate_hex_key)
    OLD_KEY=$(grep CELERY_TASK_SIGNING_KEY "$ENV_FILE" | cut -d= -f2)
    sed -i "s|CELERY_TASK_SIGNING_KEY=.*|CELERY_TASK_SIGNING_KEY=$NEW_KEY|" "$ENV_FILE"
    log_rotation "celery_signing_key" "$NEW_KEY"
    notify_rotation "celery_signing_key" "$GRACE_PERIOD"
    echo "Rotated CELERY_TASK_SIGNING_KEY."
    echo "Grace period: ${GRACE_PERIOD}s — old key still accepted for in-flight tasks."
    echo "Restart Celery workers after grace period: docker compose restart celery-worker-*"
    ;;

  pii_encryption_key)
    NEW_KEY=$(generate_hex_key)
    OLD_KEY=$(grep PII_ENCRYPTION_KEY "$ENV_FILE" | cut -d= -f2 || echo "")
    sed -i "s|PII_ENCRYPTION_KEY=.*|PII_ENCRYPTION_KEY=$NEW_KEY|" "$ENV_FILE"
    log_rotation "pii_encryption_key" "$NEW_KEY"
    notify_rotation "pii_encryption_key" "$GRACE_PERIOD"
    echo "Rotated PII_ENCRYPTION_KEY."
    echo "WARNING: Existing encrypted data must be re-encrypted with the new key."
    echo "Run backfill script or the app will use old key during grace period (${GRACE_PERIOD}s)."
    ;;

  push_token_key)
    NEW_KEY=$(generate_hex_key)
    sed -i "s|PUSH_TOKEN_ENCRYPTION_KEY=.*|PUSH_TOKEN_ENCRYPTION_KEY=$NEW_KEY|" "$ENV_FILE"
    log_rotation "push_token_key" "$NEW_KEY"
    echo "Rotated PUSH_TOKEN_ENCRYPTION_KEY."
    echo "Existing push tokens will fail decryption after restart."
    echo "Consider a gradual migration or notify users to re-register push tokens."
    ;;

  *)
    echo "Unknown secret: $SECRET_NAME"
    echo "Run '$0 detect' to see all rotatable secrets."
    exit 1
    ;;
esac
