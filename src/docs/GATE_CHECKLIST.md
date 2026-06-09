# Release Gate Checklist — v1.0.0-beta.1

Checklist for every WorkTicket release. **All gates must pass before publishing.**

---

## Code Quality

- [ ] All backend tests pass (`pytest`)
- [ ] All dashboard tests pass (`vitest`)
- [ ] All mobile tests pass (`vitest`)
- [ ] TypeScript compiles without errors (`tsc --noEmit`)
- [ ] Python type checks pass (`mypy`)
- [ ] Lint checks pass (Ruff, ESLint)
- [ ] Mutation test score >= 70% (critical modules)
- [ ] No `# type: ignore` suppressions without justification

## Security

- [ ] Gitleaks secret scan passes (no real secrets in code)
- [ ] Container vulnerability scan passes (Trivy, no HIGH/CRITICAL)
- [ ] Dependency audit passes (pip-audit, npm audit)
- [ ] No `__REQUIRED__` values in committed `.env` files
- [ ] All secret fields redacted in test fixtures
- [ ] HMAC signing key configured and non-empty
- [ ] AI endpoints return 503 when `AI_DISABLED=true`

## Migrations

- [ ] All Alembic migrations apply cleanly (`alembic upgrade head`)
- [ ] Migrations are reversible (`alembic downgrade -1` succeeds)
- [ ] No migration conflicts with `main` branch
- [ ] RLS policies verified on all tenant-scoped tables

## Infrastructure

- [ ] `docker compose up` starts all services without errors
- [ ] Backend health check returns 200 (`/healthz`, `/livez`, `/readyz`)
- [ ] Celery workers accept tasks (no connection errors)
- [ ] Redis connectivity verified (broker + cache)
- [ ] PostgreSQL connectivity verified (direct + via PgBouncer)
- [ ] No Codespaces/devcontainer references in codebase
- [ ] Docker is the only documented deployment method

## Feature Flags

- [ ] `AI_DISABLED=true` (default) — AI features are not accessible
- [ ] AI endpoints return 503 when disabled
- [ ] AI Celery tasks skip execution when disabled
- [ ] AI beat scheduled tasks skip when disabled
- [ ] Frontend `AI_FEATURES_ENABLED=false`
- [ ] All core workflows operate without AI

## Documentation

- [ ] README.md is current for this version
- [ ] CHANGELOG.md is updated with this release
- [ ] API docs are accurate (`/docs` and `/redoc`)
- [ ] `ops-guide.md` deployment steps are validated
- [ ] Runbooks are current (no stale references)
- [ ] `docs/future-ai/` inventory reflects current state
- [ ] All `package.json` repository URLs use correct org

## Git Hygiene

- [ ] Version string matches across all `package.json` and `pyproject.toml`
- [ ] No large binary files committed
- [ ] No `node_modules/` or `__pycache__/` committed
- [ ] `.gitignore` covers all generated files
- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] No unresolved merge conflicts

## Deployment (Staging)

- [ ] Staging environment deploys successfully
- [ ] Smoke tests pass on staging
- [ ] Stripe webhook endpoint responds correctly
- [ ] Clerk JWT verification works
- [ ] R2 media upload/download works
- [ ] Email and SMS notifications deliver

## Pre-Publish Verification

- [ ] All gates above checked and signed off
- [ ] Release tag created (`v1.0.0-beta.N`)
- [ ] Release notes published on GitHub
- [ ] Staging validated for 24 hours with no regressions

---

*Last updated: 2026-06-08 | Applies to: v1.0.0-beta.1 and later*
