# Changelog

All notable changes to WorkTicket are documented in this file.

---

## [1.0.0-beta.1] - 2026-06-08

### Overview

First public beta release. **Manual-first MVP** — all core workflows operate without AI. AI features are disabled by default and preserved for future reactivation.

### Features

- **Job Management** — Customer records, job creation, status tracking, activity history, team assignments
- **Estimates & Quotes** — Material and labor tracking, quote generation, approval workflows, customer delivery
- **Media** — Photo uploads, voice recordings, image optimization, Cloudflare R2 storage
- **Communications** — Email (Resend) and SMS (Twilio) notifications
- **Billing** — Stripe Checkout, billing portal, subscription management, webhook processing
- **Offline Support** — Mobile-first with SQLite persistence, offline queue, automatic retry
- **Push Notifications** — Token registration and delivery via Expo push
- **Multi-Tenant Isolation** — Row-level security with `company_id` scoping on all queries
- **Docker Deployment** — Single `docker compose up` for all services
- **CI/CD** — GitHub Actions with testing, security scanning, container vulnerability scanning, dependency auditing
- **AI Module** — Preserved in codebase, disabled via feature flags. Reactivation guide at [docs/future-ai/](./docs/future-ai/)

### Infrastructure

- PostgreSQL 16 + pgvector, Redis 7, PgBouncer connection pooling
- Celery task queue with dedicated worker pools
- Kubernetes deployment manifests (API, workers, HPA)
- Redis Sentinel HA configuration
- Prometheus alerting rules, Grafana dashboards, Loki/Promtail logging
- 16 incident response runbooks

### Security

- JWT authentication via Clerk on all endpoints
- HMAC-signed Celery task payloads
- Row-level security for tenant data isolation
- Circuit breakers and rate limiters on all external services
- Idempotency on Stripe webhooks and processing paths
- Container vulnerability scanning in CI (Trivy)
- Dependency auditing (pip-audit, npm audit)
- Secret scanning (Gitleaks)
- PII encryption at rest

### Known Limitations

See [README.md](./README.md#known-limitations). AI features are postponed to post-MVP — see [docs/future-ai/](./docs/future-ai/) for reactivation plan.

---

## Versioning

WorkTicket follows [Semantic Versioning](https://semver.org/). Beta releases use the `-beta.N` pre-release suffix.

### Prior Versions

*No prior releases. This is the initial public beta.*
