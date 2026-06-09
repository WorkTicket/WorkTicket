# ADR 009: Secrets Management Strategy

**Status:** Accepted
**Date:** 2026-06-05

## Context

WorkTicket handles sensitive credentials across multiple components:
Clerk API keys for authentication, Stripe keys for payment processing,
database credentials, Celery task signing keys, HMAC secrets for webhooks,
and API keys for Resend, Twilio, and other integrations.

Without a centralized secrets management strategy, we face these risks:
- Secrets stored in environment variables could leak via debugging output,
  error logs, or misconfigured CI pipelines
- No mechanism for automatic secret rotation
- No audit trail for secret access
- Inconsistent approach across development, staging, and production

We evaluated three options:
1. **Environment variables only** (.env files, Docker secrets)
2. **HashiCorp Vault** (centralized secrets management)
3. **Cloud-native KMS** (AWS Secrets Manager / Azure Key Vault)

## Decision

We chose **HashiCorp Vault** as the primary secrets manager with
**environment variable fallback** for local development and CI.

### Architecture

```
Production:         Vault Server → Application (via vault-py SDK)
Staging:            Vault Server → Application (via vault-py SDK)
CI/CD:              Vault Agent injector → GitHub Actions secrets
Local dev:          Vault (optional) → .env fallback
```

### Key Design Decisions

1. **Primary: Vault with AppRole auth**: Each service authenticates to
   Vault using a unique AppRole with read-only access to its specific
   secrets path. No service can read another service's secrets.

2. **Fallback: Environment variables**: If Vault is unreachable (local
   development, CI without Vault agent), the application reads from
   `os.environ` with a `VAULT_UNAVAILABLE` log warning. The env var
   fallback path mirrors the Vault path structure.

3. **Secret rotation**: All secrets have a default TTL of 30 days.
   Vault's lease renewal mechanism handles rotation transparently.
   Static secrets (database passwords, API keys) use Vault's database
   secret engine with automated rotation every 7 days.

4. **Dynamic secrets**: Database credentials are generated on-demand
   by Vault's PostgreSQL secret engine with a 1-hour lease, eliminating
   long-lived database passwords.

5. **Audit logging**: Vault audit logs record every secret access,
   stored to a separate log sink for compliance and forensics.

### Secret Categories and Rotation

| Category | TTL | Rotation Period | Fallback Source |
|----------|-----|----------------|-----------------|
| Database credentials | 1h (dynamic) | Per-lease | `DATABASE_URL` env |
| API keys (Stripe, Clerk) | 30d (static) | 7d automated | `.env` file |
| HMAC signing keys | 90d (static) | Manual with grace | `CELERY_TASK_SIGNING_KEY` |
| Session encryption keys | 30d (static) | 7d automated | `SESSION_SECRET` env |
| Infrastructure secrets | 90d (static) | Manual | Docker secrets |

## Consequences

### Positive
- **Centralized management**: All secrets managed in one place with
  consistent access controls
- **Automated rotation**: Database credentials rotate hourly; API keys
  rotate weekly without application restart
- **Audit trail**: Complete visibility into which service accessed
  which secret and when
- **Graceful degradation**: Environment variable fallback ensures
  continued operation when Vault is unavailable
- **Least privilege**: Each service has access only to its own secrets

### Negative
- **Operational complexity**: Vault requires its own infrastructure
  (cluster, storage backend, monitoring)
- **Initial setup overhead**: AppRole configuration, policy creation,
  and service integration require upfront engineering effort
- **Single point of failure**: If both Vault is down and env vars
  are misconfigured, services cannot start
- **Learning curve**: Team must understand Vault's authentication,
  secret engines, and lease management concepts

### Security Boundaries
- Vault server runs in its own network segment, accessible only by
  application services
- Vault storage backend (Raft integrated storage) is encrypted at rest
- Vault is sealed at rest; unseal keys are distributed across team
  members (Shamir's Secret Sharing, 3 of 5 threshold)
- Secrets are never logged; the secrets client strips sensitive
  values from exception messages and stack traces
