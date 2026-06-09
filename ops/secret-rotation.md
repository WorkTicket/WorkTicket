# Item 15 — Secret Rotation Ops Procedures

## Secret Inventory

| Secret | Location | Rotation Period | Auto-Rotatable |
|---|---|---|---|
| `POSTGRES_PASSWORD` | .env, Docker compose | 90 days | No (DB user) |
| `REDIS_PASSWORD` | .env, Docker compose | 90 days | No (config) |
| `SECRET_KEY` | .env | 180 days | No |
| `STRIPE_SECRET_KEY` | .env, Stripe dashboard | 365 days | Yes (Stripe API) |
| `STRIPE_WEBHOOK_SECRET` | .env, Stripe dashboard | 365 days | Yes (Stripe API) |
| `CLERK_SECRET_KEY` | .env, Clerk dashboard | 365 days | Yes (Clerk API) |
| `R2_ACCESS_KEY_ID` | .env, Cloudflare dashboard | 180 days | Yes (R2 API) |
| `R2_SECRET_ACCESS_KEY` | .env, Cloudflare dashboard | 180 days | Yes (R2 API) |
| `SENTRY_DSN` | .env, Sentry dashboard | Per-project | No |
| `POSTHOG_API_KEY` | .env, PostHog dashboard | Per-project | No |
| `TWILIO_AUTH_TOKEN` | .env, Twilio dashboard | 365 days | Yes (Twilio API) |
| `RESEND_API_KEY` | .env, Resend dashboard | 365 days | Yes |
| `METRICS_ACCESS_TOKEN` | .env | 90 days | No |

## Rotation Script — `ops/scripts/rotate-secrets.sh`
```bash
#!/bin/bash
# Secret rotation script for WorkTicket
# Usage: ./rotate-secrets.sh <secret-name>

set -euo pipefail

SECRET_NAME="${1:-}"
ENV_FILE="${2:-.env}"

if [ -z "$SECRET_NAME" ]; then
  echo "Usage: $0 <secret-name> [env-file]"
  echo "Available: postgres_password redis_password secret_key stripe_webhook metrics_token"
  exit 1
fi

generate_password() {
  python -c "import secrets; print(secrets.token_urlsafe(32))"
}

case "$SECRET_NAME" in
  postgres_password)
    NEW_PASS=$(generate_password)
    # Requires DB superuser to alter role
    echo "ALTER ROLE postgres WITH PASSWORD '$NEW_PASS';" | docker compose exec -T postgres psql -U postgres
    sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$NEW_PASS/" "$ENV_FILE"
    echo "Rotated postgres_password. Restart backend services: docker compose up -d backend celery-worker-* celery-beat"
    ;;

  redis_password)
    NEW_PASS=$(generate_password)
    # Update Redis config (requires config rewrite)
    docker compose exec -T redis-broker redis-cli CONFIG SET requirepass "$NEW_PASS"
    docker compose exec -T redis-cache redis-cli CONFIG SET requirepass "$NEW_PASS"
    # Save config
    docker compose exec -T redis-broker redis-cli CONFIG REWRITE
    docker compose exec -T redis-cache redis-cli CONFIG REWRITE
    # Update env
    sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$NEW_PASS/" "$ENV_FILE"
    echo "Rotated redis_password. Restart backend services."
    ;;

  secret_key)
    NEW_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_KEY/" "$ENV_FILE"
    echo "Rotated SECRET_KEY. Restart all services to pick up new key."
    ;;

  stripe_webhook)
    echo "Manual step required:"
    echo "1. Go to Stripe Dashboard → Developers → Webhooks → WorkTicket endpoint"
    echo "2. Click 'Reveal live key' → 'Roll signing secret'"
    echo "3. Update STRIPE_WEBHOOK_SECRET in $ENV_FILE"
    echo "4. Restart backend: docker compose up -d backend"
    ;;

  metrics_token)
    NEW_TOKEN=$(generate_password)
    sed -i "s/METRICS_ACCESS_TOKEN=.*/METRICS_ACCESS_TOKEN=$NEW_TOKEN/" "$ENV_FILE"
    echo "Rotated METRICS_ACCESS_TOKEN."
    ;;

  *)
    echo "Unknown secret: $SECRET_NAME"
    exit 1
    ;;
esac
```

## Automated Rotation Schedule (Celery Beat)

Add to `src/backend/celery_app.py` beat_schedule:
```python
"rotate-metrics-token-every-90-days": {
    "task": "rotate_metrics_token",
    "schedule": 7776000.0,  # 90 days
    "options": {"expires": 86400.0},
},
```

## Zero-Downtime Rotation Procedure

1. **Phase 1 — Dual Auth (Stripe, Clerk, R2)**: Update app to accept both old and new credentials for 5 minutes
2. **Phase 2 — Roll**: Update env var in deployment
3. **Phase 3 — Verify**: Run `curl -f https://api.example.com/health` and check readiness
4. **Phase 4 — Deprecate Old**: Remove old credential from service

## Breach Response

If a secret is compromised:
```bash
# 1. Immediately rotate the compromised secret
./ops/scripts/rotate-secrets.sh <compromised-secret>

# 2. Revoke all existing sessions
docker compose exec redis-broker redis-cli KEYS "session_*" | xargs docker compose exec redis-broker redis-cli DEL

# 3. Force-logout all users
# (implement forced token version increment)

# 4. Audit access logs for the past 72h
docker compose logs --since 72h backend | grep -E "401|403|invalid token|unauthorized"

# 5. Notify security team
```

## Verification
```bash
# Check secret age in env file
grep -E "(PASSWORD|SECRET|TOKEN)" .env | while IFS='=' read -r key value; do
  echo "$key: ${#value} chars"
done

# Verify all secrets are non-default
if grep -q "changeme" .env; then
  echo "WARNING: Default passwords still in use!"
fi
```
