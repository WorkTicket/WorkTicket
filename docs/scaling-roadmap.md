# WorkTicket Scaling Roadmap

> All costs in USD/month using standard cloud pricing (Hetzner / Vultr / DigitalOcean equivalent tiers).

---

## 100-Tenant Profile (Current Beta Target)

### Database Strategy
- **Engine:** Single PostgreSQL 16 instance
- **Pooling:** PgBouncer with transaction pooling mode, pool size 50
- **Storage:** 100 GB SSD, daily pg_dump backups to object storage
- **Indexing:** Standard B-tree indexes on `company_id`, `tenant_id`, `created_at`

### Redis Strategy
- **Topology:** Single standalone Redis instance
- **Separation:** Broker (Celery) and cache on same instance, separate logical DBs (db0=broker, db1=cache)
- **Memory:** 2-4 GB allocated
- **Persistence:** AOF every 1 second, RDB snapshot every 6 hours

### AI Strategy
- **Inference:** Single Ollama instance
- **Models:** `llama3.1:8b` (text) + `llama3.2-vision` (image/OCR)
- **Hardware:** Single consumer GPU (RTX 3060/4060, 12 GB VRAM) or equivalent cloud GPU
- **Concurrency:** 1-2 concurrent AI requests max

### Queue Strategy
- **Broker:** Single Redis instance (shared with cache, db0)
- **Workers:** 4 dedicated Celery queues:
  - `ai_text` — NLP classification, summarization
  - `ai_audio` — Transcription, TTS
  - `ai_image` — OCR, image classification
  - `default` — Email, webhooks, exports
- **Concurrency:** 2-4 worker processes per queue
- **Scheduler:** Single `celery beat` instance for periodic tasks

### Estimated Monthly Infrastructure Cost: **$150–300**

| Component | Spec | Estimated Cost |
|-----------|------|---------------|
| PostgreSQL | 2 vCPU, 4 GB RAM, 100 GB SSD | $50 |
| Redis | 1 vCPU, 2 GB RAM | $30 |
| AI (Ollama) | 4 vCPU, 16 GB RAM, 1x GPU 12 GB | $80 |
| Workers | 4 vCPU, 8 GB RAM (shared) | $40 |
| Monitoring | Grafana + Prometheus + Loki (minimal) | $20 |
| **Total** | | **$220** |

### Key Metrics
- **Jobs/day:** 500–2,000
- **AI requests/day:** 50–200
- **Active tenants:** up to 100
- **p50 API latency:** <200ms (reads), <500ms (writes)
- **p99 API latency:** <2s
- **AI job latency:** <60s (text), <180s (audio/vision)

### Bottleneck Areas
| Area | Symptom | Mitigation |
|------|---------|------------|
| Ollama GPU memory | OOM on concurrent vision requests | Queue depth limiting, model offloading |
| PostgreSQL I/O | Slow analytics queries on `work_tickets` table | Materialized views, query timeout (30s) |
| Redis memory pressure | Evictions under high job volume | Increase memory, TTL tuning |
| Single Celery beat | Missed schedules if beat process dies | Healthcheck with auto-restart |

---

## 1000-Tenant Profile (Growth Target)

### Database Strategy
- **Primary:** PostgreSQL 16 with 4 vCPU, 16 GB RAM, 500 GB NVMe
- **Read Replicas:** 2 async streaming replicas for analytics/reporting queries
- **Pooling:** PgBouncer with transaction pooling, pool size 150
- **Partitioning:** `pg_partman` for time-series tables (`work_tickets`, `audit_log`) by month
- **Backups:** WAL archiving to S3-compatible storage (point-in-time recovery, 7-day retention)

### Redis Strategy
- **Topology:** Redis Sentinel HA
  - 3 Sentinels (quorum=2)
  - 1 Primary + 2 Replicas
- **Separation:** Dedicated broker instance + dedicated cache instance
- **Memory:** 8 GB per instance
- **Persistence:** AOF every 1s on primary, RDB on replicas

### AI Strategy
- **Option A (cost-optimized):** Multi-GPU Ollama
  - 1 GPU dedicated to `llama3.1:8b` (text)
  - 1 GPU dedicated to `llama3.2-vision` (image)
  - Load distribution via model-aware proxy
- **Option B (throughput-optimized):** NVIDIA Triton Inference Server
  - Dynamic batching, concurrent model execution
  - 2x GPU minimum
- **Fallback:** OpenAI-compatible API as overflow buffer when queue depth > 50

### Queue Strategy
- **Broker:** Dedicated Redis instance (Sentinel-managed)
- **Per-Queue Autoscaling:** `docker-compose.autoscale.yml` profile
  - `ai_text` workers scale 2–16 based on queue depth
  - `ai_audio` workers scale 2–8 based on queue depth
  - `ai_image` workers scale 2–8 based on queue depth
  - `default` workers scale 4–16 based on queue depth
- **Scheduler:** Single `celery beat` with redundant standby (leader election via Redis lock)

### Tenant-Aware Routing
- Identify top 10% tenants by job volume
- Dedicated worker pools for high-volume tenants
- Remaining 90% share a general pool
- Route via custom Celery router (`TenantAwareRouter`)

### Estimated Monthly Infrastructure Cost: **$800–2,000**

| Component | Spec | Estimated Cost |
|-----------|------|---------------|
| PostgreSQL Primary | 4 vCPU, 16 GB RAM, 500 GB NVMe | $150 |
| PostgreSQL Replicas | 2x 2 vCPU, 8 GB RAM, 500 GB SSD | $100 |
| Redis (broker) | 2 vCPU, 8 GB RAM | $60 |
| Redis (cache) | 2 vCPU, 8 GB RAM | $60 |
| AI/GPU | 2x GPU 16 GB or equivalent cloud GPU | $400 |
| Workers | 8 vCPU, 16 GB RAM | $200 |
| Monitoring | Grafana + Prometheus + Loki + Alertmanager | $80 |
| **Total** | | **$1,050** |

### Key Metrics
- **Jobs/day:** 5,000–20,000
- **AI requests/day:** 500–2,000
- **Active tenants:** up to 1,000
- **p50 API latency:** <150ms (reads), <400ms (writes)
- **p99 API latency:** <1.5s
- **AI job latency:** <30s (text), <120s (audio/vision)
- **Read replica lag:** <100ms

---

## 10,000-Tenant Profile (Scale Target)

### Database Strategy
- **Primary approach:** Horizontal sharding by `company_id` ranges
  - 4–8 shards, each a PostgreSQL 16 primary with 1–2 replicas
  - Shard map stored in a lightweight metadata DB
- **Alternative:** Citus distributed PostgreSQL (if staying on single logical DB)
  - Distributed tables for `work_tickets`, `audit_log`
  - Reference tables for `tenants`, `plans`, `configurations`
- **Pooling:** PgBouncer per shard, pool size 100 per shard
- **Partitioning:** `pg_partman` per shard (monthly time-series partitions)
- **Backups:** Per-shard WAL archiving + daily logical backup of shard map

### Redis Strategy
- **Topology:** Redis Cluster (native sharding)
  - Minimum 3 primary + 3 replica nodes
  - Hash-tag based key distribution: `{tenant_id}:key_name`
- **Separation:** Separate clusters for broker and cache
- **Memory:** 16 GB per node
- **Persistence:** AOF on all primaries, RDB snapshots staggered across nodes

### AI Strategy
- **Primary:** GPU cluster with load balancer (HAProxy or Envoy)
  - 4–8 GPUs, model replicas on dedicated nodes
  - Triton Inference Server with model ensembles
- **Overflow:** Managed inference API (OpenAI, Anthropic, or Fireworks) for queue overflow
  - Trigger when local queue depth > 100 and avg wait > 30s
  - Cost-aware routing (route cheap models locally, expensive ones to API selectively)
- **Caching:** Semantic cache for frequent prompts (Redis + vector similarity)

### Queue Strategy
- **Broker:** Per-shard Redis Cluster nodes (broker cluster)
- **Workers:** Per-shard Celery workers
  - Each shard has independent `ai_text`, `ai_audio`, `ai_image`, `default` queues
- **Scheduler:** Dedicated `celery beat` per shard (no cross-shard scheduling)
- **Orchestration:** Kubernetes or Docker Swarm with per-shard namespace isolation

### Tenant-Dedicated Infrastructure
- **Enterprise tier:** Isolated PostgreSQL shard + Redis nodes + dedicated worker pool
- **Provisioning:** Terraform/Pulumi for per-tenant infrastructure-as-code
- **Networking:** VPC/subnet isolation for enterprise tenants
- **Billing:** Usage-based with dedicated resource surcharge

### Estimated Monthly Infrastructure Cost: **$5,000–15,000**

| Component | Spec | Estimated Cost |
|-----------|------|---------------|
| PostgreSQL Shards | 4x primary + 4x replica, 8 vCPU 32 GB each | $1,500 |
| Redis Cluster (broker) | 6 nodes, 4 vCPU 16 GB each | $400 |
| Redis Cluster (cache) | 6 nodes, 4 vCPU 16 GB each | $400 |
| AI GPU Cluster | 4–8 GPUs, load-balanced | $3,000 |
| Workers | 32 vCPU, 64 GB total (per-shard pools) | $1,500 |
| Monitoring | Full stack + distributed tracing | $300 |
| Load Balancers/Networking | HAProxy, VPC, bandwidth | $200 |
| **Total** | | **$7,300** |

### Key Metrics
- **Jobs/day:** 50,000–200,000
- **AI requests/day:** 5,000–20,000
- **Active tenants:** up to 10,000
- **p50 API latency:** <100ms (reads), <300ms (writes)
- **p99 API latency:** <1s
- **AI job latency:** <15s (text), <90s (audio/vision)
- **Shard imbalance tolerance:** 2:1 (max shard / min shard)

---

## Migration Triggers

### 100 → 1000 (Growth Tier)
| Trigger | Threshold | Measurement |
|---------|-----------|-------------|
| DB pool utilization | >70% sustained for 1 hour | `pg_stat_activity` via Prometheus |
| Redis memory usage | >80% of maxmemory | `redis_memory_used_bytes / redis_maxmemory` |
| AI queue depth | >100 pending jobs sustained for 30 min | `celery_queue_length` metric |
| API p99 latency | >3s sustained for 3 hours | Load balancer metrics |
| Tenant count | >80 active tenants | DB query on `tenants` table |
| Customer complaint rate | >2 latency-related tickets/week | Support dashboard |

### 1000 → 10,000 (Scale Tier)
| Trigger | Threshold | Measurement |
|---------|-----------|-------------|
| DB write throughput | >80% of instance max IOPS | Cloud provider metrics |
| Replica lag | >5s sustained for 10 min | `pg_stat_replication` |
| Tenant isolation incidents | Any cross-tenant data leak or noisy neighbor | Incident tracker |
| Enterprise tier demand | >10% of tenants requesting dedicated infra | Sales/support pipeline |
| AI overflow API usage | >30% of AI requests routed to external API | Routing proxy metrics |
| Active tenant count | >800 active tenants | DB query |
| Queue starvation | Any queue >500 backlog for >5 min | Celery metrics |

---

## Cost Projections Table

| Tier | Tenants | DB | Redis | AI/GPU | Workers | Monitoring | Total/mo |
|------|---------|-----|-------|--------|---------|------------|----------|
| Beta | 100 | $50 | $30 | $80 | $40 | $20 | $220 |
| Growth | 1,000 | $250 | $120 | $400 | $200 | $80 | $1,050 |
| Scale | 10,000 | $1,500 | $800 | $3,000 | $1,500 | $300 | $7,100 |

> **Note:** Enterprise tenant dedicated infrastructure costs are additive and not included in base Scale tier. Per-tenant isolated stack adds approximately $200–500/mo depending on GPU requirements.

---

## Anti-Patterns to Avoid

### 1. Don't Shard Prematurely
- **Rule:** Sharding complexity cost exceeds hardware cost until ~500 tenants or sustained IOPS pressure.
- **Why:** Sharding introduces cross-shard query limitations, distributed transaction complexity, and operational overhead (resharding, backup coordination).
- **Do instead:** Scale vertically first (larger instance), then add read replicas, then partition time-series tables with `pg_partman`. Only shard when these are exhausted.

### 2. Don't Use Redis Pub/Sub for Critical State
- **Rule:** Redis pub/sub is fire-and-forget. Messages are lost if no subscriber is connected.
- **Why:** Critical state transitions (job lifecycle, tenant provisioning status, billing events) must survive subscriber restarts.
- **Do instead:** Use Redis Streams with consumer groups + dual-write to PostgreSQL as source of truth. Streams persist messages and support at-least-once delivery.

### 3. Don't Assume Uniform Tenant Size
- **Rule:** One tenant can be 100x the size of another in job volume, storage, and AI usage.
- **Why:** Uniform distribution assumptions lead to hotspot shards, noisy neighbor problems, and unpredictable latency for small tenants.
- **Do instead:** Implement tenant sizing metrics early. Use weighted routing. Offer dedicated infrastructure for top-percentile tenants. Design partition keys that distribute large tenants across shards (avoid hashing on tenant_id alone if sharding on it — use sub-partitioning by ticket_id for the largest tenants).

### 4. Don't Couple Queue Lifecycle to Request Lifecycle
- **Rule:** Celery task TTLs and result backends should not block HTTP request workers.
- **Why:** Long-running AI tasks can exhaust WSGI/ASGI workers if clients poll synchronously.
- **Do instead:** Always use async task result polling from the client. Set Celery `result_expires` aggressively. Use a dedicated results backend (Redis db2) separate from the broker.

### 5. Don't Skip Monitoring at Beta Stage
- **Rule:** You cannot optimize what you don't measure.
- **Why:** Scaling bottlenecks are often invisible until they become outages.
- **Do instead:** From day one, export: queue depth per queue, DB pool utilization, Redis memory and hit ratio, AI inference latency p50/p99, per-tenant job volume distribution. Grafana dashboards with these panels should exist before the first paying tenant.
