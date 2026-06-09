# ADR 004: HMAC Task Signing for Celery Payloads

**Status:** Accepted
**Date:** 2026-06-05

## Context

Celery tasks carry payloads that include tenant context (company_id),
job IDs, and AI processing parameters. If an attacker could forge task
payloads, they could:
- Execute AI processing on behalf of another tenant
- Bypass per-company quotas
- Inject malicious data into AI pipelines

## Decision

All Celery task payloads are **HMAC-signed** using the
`CELERY_TASK_SIGNING_KEY`. The signature includes the task name,
all arguments, and a version identifier to support key rotation.

### Signature format:
```
base64(HMAC-SHA256(key, task_name + ":" + json(args) + ":" + version))
```

### Key rotation support:
- A grace period allows accepting signatures from the previous key
- New tasks are always signed with the current key
- Rotating keys does not invalidate in-flight tasks

### Fail-closed behavior:
If signature verification fails, the task is rejected immediately.
No fallback or silent acceptance of unsigned tasks.

## Consequences

- **Task payload integrity** is cryptographically guaranteed
- **Key rotation** requires updating `CELERY_TASK_SIGNING_KEY` in
  the environment and restarting workers
- **Performance**: HMAC computation is negligible (~microseconds)
  compared to AI processing times (seconds to minutes)
