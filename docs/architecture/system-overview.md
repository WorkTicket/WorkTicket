# System Overview

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Mobile Client | React Native, Expo, Zustand, TanStack Query | Field technician app with offline support |
| Dashboard | Next.js, Tailwind CSS, shadcn/ui | Office staff admin interface |
| Backend API | FastAPI, SQLAlchemy (async), Pydantic | RESTful API with OpenAPI docs |
| Task Queue | Celery + Redis | Async AI processing, media handling, billing |
| Database | PostgreSQL 16 + pgvector | Primary data store with vector search |
| AI Text | Ollama (llama3.1) | Job analysis and estimate drafting |
| AI Vision | Ollama (llama3.2-vision) | Photo analysis |
| AI Audio | faster-whisper | Voice note transcription |
| Auth | Clerk | JWT-based authentication |
| Object Storage | Cloudflare R2 | Media file storage |
| Payments | Stripe | Subscriptions, checkout, billing |
| Notifications | Twilio (SMS), Resend (email) | Customer and team alerts |
| Monitoring | Sentry, PostHog | Error tracking and analytics |
| Container | Docker, Docker Compose | Local dev and production deployment |

## Service Boundaries

### Backend (Monolith Modules)

- **AI Module** — orchestrator, Ollama gateway, circuit breaker, rate limiter, whisper proxy
- **Billing Module** — Stripe webhooks, subscription management, quotas, usage ledger
- **Estimates Module** — estimate generation, audit snapshots, state machine
- **Jobs Module** — job CRUD, customer records, status workflows
- **Media Module** — upload pipeline, image optimization, malware scan, R2 storage
- **Notifications Module** — email (Resend), SMS (Twilio), push notifications (Expo)
- **Auth Module** — Clerk JWT verification, token versioning, deactivation
- **Analytics Module** — event tracking, paginated queries, business metrics
- **Quotes Module** — quote generation, approval workflows, delivery

### Supporting Services

- **Whisper Service** — standalone HTTP service for faster-whisper ASR
- **Nginx** — reverse proxy with rate limiting and TLS termination
- **Celery Workers** — background task processing for AI, billing, media
- **Redis** — broker, result backend, rate limiter, cache
- **PostgreSQL** — primary database with Row-Level Security

### Frontend Clients

- **Mobile App** — technician-facing, offline-first with SQLite-backed queue
- **Web Dashboard** — office staff admin, real-time updates via polling

## Data Flow (Primary Paths)

### Job Lifecycle

```
Mobile: Create Job → Upload Media → (AI Process) → Review Draft → Approve Quote → Send
                                    ↓
Dashboard: View Jobs → Manage Customers → Generate Reports → Billing
```

### AI Processing

```
Mobile upload → API → Celery Task → Ollama/faster-whisper → Structured Output → Review → Approve
                 ↓
          Circuit Breaker + Rate Limiter + Audit Log
```

### Billing

```
Stripe Webhook → Idempotency Check → Subscription Update → Usage Ledger → Quota Enforcement
```
