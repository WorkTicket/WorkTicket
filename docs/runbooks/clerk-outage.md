# Clerk Authentication Outage Runbook

## Overview

WorkTicket relies on Clerk for JWT-based authentication. If Clerk's JWKS endpoint or authentication service experiences an outage, new user sign-ins will fail. Existing valid JWTs continue to work until expiration.

## Severity Assessment

| Scenario | Severity | User Impact | Auto-Recovery |
|----------|----------|-------------|---------------|
| Clerk JWKS unreachable (<5 min) | SEV3 | New sign-ins fail, existing sessions work | Auto-recover when Clerk recovers |
| Clerk JWKS unreachable (>15 min) | SEV2 | All new sign-ins fail, some token refreshes fail | Manual intervention may be needed |
| Clerk API completely down | SEV1 | All auth operations fail | Requires Clerk recovery |
| Clerk returns invalid JWKS | SEV1 | All auth fails (existing sessions also break) | Immediate manual intervention |

## Detection

### Prometheus Alerts
- `WorkTicketAuthLatencyHigh` — auth response time > 2s P95 for >5min
- `WorkTicketAuthErrorRateHigh` — auth error rate > 5% for >5min

### Logs to monitor
```
grep "JWT verification not configured\|Token expired\|Invalid token\|JWKS"
```

### Health check
```
curl -f https://<your-clerk-domain>/.well-known/jwks.json
```

## Mitigation Steps

### Step 1: Verify the outage is Clerk-related

```bash
# Check if Clerk is down
curl -f https://api.clerk.com/v1/health

# Check JWKS endpoint specifically
curl -f https://<CLERK_JWT_ISSUER>/.well-known/jwks.json
```

### Step 2: Check JWKS caching status

WorkTicket caches JWKS keys in Redis with a 1-hour TTL and locally in memory. If the outage is brief (<1 hour), cached keys will serve requests.

```bash
# Check Redis for cached keys
redis-cli KEYS "auth:jwks:*"
redis-cli TTL "auth:jwks:<kid>"
```

### Step 3: Extend cache TTL if possible (NEEDS MANUAL CODE CHANGE)

If Clerk is expected to be down for an extended period (unlikely given their SLA), but the existing cached JWKS keys need to be preserved longer:

```python
# In app/auth/dependencies.py, temporarily increase:
# _JWKS_CACHE_TTL = 86400  # 24 hours
# _redis_jwks_ttl = 86400
```

**DO NOT** make this change without engineering approval — tokens from revoked users would remain valid for the extended period.

### Step 4: Communication

- Post status update to status page
- Notify users via in-app banner (if possible) or email
- Update internal Slack #incidents channel

## Recovery

1. Monitor Clerk status at https://status.clerk.com
2. Once Clerk recovers, JWKS cache will refresh on the next key rotation cycle
3. Verify:
   ```bash
   curl -s https://your-domain/livez
   curl -s https://your-domain/healthz
   ```
4. Run a test sign-in flow to confirm recovery
5. Post resolution update to status page

## Future Backup Auth Architecture

The following backup strategy is **planned for GA** (not currently implemented):

1. **Service Account API Key** fallback: Generate a long-lived Clerk API key stored in Vault. If JWKS verification fails, use the Clerk Backend API `GET /v1/users/{id}` to validate tokens server-side instead of locally.
2. **Emergency admin bypass** (break-glass): A single-use bypass token stored in Vault that grants admin access. Logged, alerted, and rotated after every use.
3. **Multiple identity provider**: Support both Clerk and Auth0 as redundant IdPs.

## See Also

- [Clerk Status Page](https://status.clerk.com)
- [Clerk API Reference](https://clerk.com/docs/reference/backend-api)
- [WorkTicket Auth Dependencies](../../src/backend/app/auth/dependencies.py)
