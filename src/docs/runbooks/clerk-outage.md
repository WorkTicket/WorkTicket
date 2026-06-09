# Runbook: Clerk Outage

## Impact
- New JWTs cannot be verified
- Existing sessions: cached JWKS keys still work (up to 1 hour TTL)
- After cache expiry: all authenticated requests return 401

## Detection
- Auth failure rate spike
- /readyz shows JWKS fetch failures

## Recovery
1. Wait for Clerk recovery (typically minutes)
2. No manual intervention needed — Redis cache auto-recovers
3. If prolonged: deploy emergency static JWKS via env var

## Emergency Access
- If Clerk is down and access is critical:
  - Set `CLERK_JWT_ISSUER` to a self-hosted JWKS endpoint
  - Or temporarily disable auth for internal IPs
