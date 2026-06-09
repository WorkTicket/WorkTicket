# Future AI Development

This directory contains the complete AI asset inventory, reactivation guides, and development logs for all AI functionality in WorkTicket.

**Current Status:** All AI features are **disabled** (MVP v1 is manual-first).  
**Reactivation Target:** Post-revenue, after product-market fit validation.

## Document Index

| Document | Purpose |
|---|---|
| [ai-asset-inventory.md](./ai-asset-inventory.md) | Complete inventory of all AI files, endpoints, workers, DB tables, env vars, services |
| [ai-reactivation-guide.md](./ai-reactivation-guide.md) | Step-by-step checklist to re-enable AI in production |
| [ai-architecture.md](./ai-architecture.md) | Architecture overview, design intent, data flow, service interactions |
| [ai-infrastructure-plan.md](./ai-infrastructure-plan.md) | Infrastructure requirements for AI (cloud vs self-hosted) |
| [ai-roadmap.md](./ai-roadmap.md) | Future improvements, performance, scalability, cost optimization |
| [feature-notes/](./feature-notes/) | Per-feature development logs with reactivation steps |

## Quick Reference

### How to Re-enable AI

1. Set `AI_DISABLED=false` in `src/backend/.env` (or env var `AI_DISABLED=false`)
2. Or set `FEATURE_AI_DISABLED=false` (feature flag override)
3. Start AI services: `docker compose --profile ai up -d`
4. Wait for Ollama to pull models (2-5 min on first startup)
5. AI endpoints and workers become active automatically

### Feature Flag Controls

| Flag | Controls | Default |
|---|---|---|
| `AI_DISABLED` env var / `ai_disabled` setting | Master kill switch for all AI | `true` |
| `FEATURE_AI_DISABLED` env var | Feature flag override | `true` |
| `ai_celery_async` | Async vs sync Celery dispatch | `true` |
