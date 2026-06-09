# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 1.0.x (beta) | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please do **not** open a public issue.

**Report via email:** security@workticket.dev

Include:
- Type of vulnerability
- Steps to reproduce
- Affected versions
- Potential impact

You should receive a response within 48 hours. If you don't, please follow up.

## Disclosure Policy

1. Acknowledge receipt within 48 hours.
2. Investigate and determine remediation.
3. Release a fix and disclose after the fix is available.

## Security Practices

- JWT authentication (Clerk) on all endpoints
- Multi-tenant isolation via `company_id` scoping on all queries (Row-Level Security)
- HMAC-signed Celery task payloads prevent tampering
- Secrets never committed to version control
- Environment variables follow `.env.example` templates with safe placeholders
- Dependencies audited regularly via automated CI workflows
- Container images scanned for vulnerabilities (Trivy)
- Secret scanning on every push (Gitleaks)
- Idempotency enforced on Stripe webhook processing
- PII encrypted at rest

## AI Security

AI features are **disabled** in v1.0.0-beta.1. When reactivated:
- All AI outputs require explicit human approval before reaching customers
- Outputs with low confidence are automatically rejected
- Circuit breakers and rate limiters protect the AI pipeline
- Prompt injection defense is integrated at multiple layers
- See [docs/future-ai/](./docs/future-ai/) for complete security architecture

## Known Security Constraints

See [Known Limitations](./README.md#known-limitations) in the README.
