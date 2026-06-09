# SLI-to-Metric Mapping

Each SLI defined in the performance baseline is mapped to specific Prometheus metrics with query expressions for dashboard panels and alert rules.

## 1. API Availability (99.9%)

| Aspect | Detail |
|--------|--------|
| **Metric** | `workticket_http_request_duration_seconds_count` |
| **SLI query** | `1 - (sum(rate(workticket_http_request_duration_seconds_count{status=~"5.."}[5m])) / sum(rate(workticket_http_request_duration_seconds_count[5m])))` |
| **Alert query** | `sum(rate(workticket_http_request_duration_seconds_count{status=~"5.."}[5m])) / sum(rate(workticket_http_request_duration_seconds_count[5m])) > 0.001` |
| **Dashboard panel** | `workticket-slos` → row "SLI / SLO Targets" → "SLO: API Availability" |
| **Error budget** | 43.2 minutes/month allowed 5xx time (99.9% = 43.8 min downtime) |

## 2. Latency P95 (500ms)

| Aspect | Detail |
|--------|--------|
| **Metric** | `workticket_http_request_duration_seconds_bucket` (histogram) |
| **SLI query** | `histogram_quantile(0.95, sum(rate(workticket_http_request_duration_seconds_bucket[5m])) by (le))` |
| **Per-endpoint-class query** | `histogram_quantile(0.95, sum(rate(workticket_http_request_duration_seconds_bucket[5m])) by (le, endpoint_class))` |
| **Dashboard panel** | `workticket-slos` → row "API Health" → "API: Latency Percentiles" and "Latency: By Endpoint Class" |
| **Labels** | `endpoint_class` = `critical` / `normal` / `report` |

## 3. Latency P99 (2000ms)

| Aspect | Detail |
|--------|--------|
| **Metric** | `workticket_http_request_duration_seconds_bucket` (histogram) |
| **SLI query** | `histogram_quantile(0.99, sum(rate(workticket_http_request_duration_seconds_bucket[5m])) by (le))` |
| **Dashboard panel** | `workticket-slos` → row "API Health" → "API: Latency Percentiles" |

## 4. Error Rate (0.1%)

| Aspect | Detail |
|--------|--------|
| **Metric** | `workticket_http_request_duration_seconds_count` |
| **SLI query** | `sum(rate(workticket_http_request_duration_seconds_count{status=~"5.."}[5m])) / sum(rate(workticket_http_request_duration_seconds_count[5m]))` |
| **Dashboard panels** | `workticket-slos` → row "API Health" → "API: Error Rate by Status" |

## 5. Database Availability (99.95%)

| Aspect | Detail |
|--------|--------|
| **Primary metric** | `workticket_db_pool_utilization` |
| **SLI query** | `workticket_db_pool_utilization < 0.85` |
| **Secondary metric** | `workticket_db_circuit_cooldown_seconds` |
| **Circuit breaker query** | `workticket_db_circuit_cooldown_seconds > 0` (circuit open/cooldown) |
| **Connection pool saturation** | `workticket_db_pool_utilization` |
| **PgBouncer backlog** | `workticket_pgbouncer_queue_depth` |
| **Dashboard row** | `workticket-slos` → row "Database" |
| **Alerts** | `DatabasePoolSaturation` (>80%), `DatabasePoolExhausted` (>95%) |
| **Error budget** | 21.6 minutes/month allowed DB unavailability |

## 6. Redis Availability (99.95%)

| Aspect | Detail |
|--------|--------|
| **Primary metric** | `workticket_rate_limiter_redis_available` |
| **SLI query** | `workticket_rate_limiter_redis_available == 1` |
| **Memory metric** | `redis_memory_used_bytes / redis_memory_max_bytes` |
| **Eviction metric** | `rate(redis_keyspace_evicted_total[5m])` |
| **Write failure metric** | `increase(workticket_redis_write_failures_total[5m])` |
| **Dashboard row** | `workticket-slos` → row "Redis" |
| **Alerts** | `RateLimiterRedisDown`, `BrokerRedisMemoryHigh`, `BrokerRedisWriteFailures`, `RedisEvictionsDetected` |
| **Error budget** | 21.6 minutes/month allowed Redis unavailability |

## 7. Celery Queue Health (99%)

| Aspect | Detail |
|--------|--------|
| **Primary metric** | `workticket_celery_task_latency_seconds` (summary, quantile=0.95) |
| **SLI query** | `workticket_celery_task_latency_seconds{quantile="0.95"} < 60` |
| **Queue depth** | `workticket_queue_depth{queue=~"default|ai_text|ai_audio|ai_image|beat"}` |
| **Worker active** | `workticket_celery_worker_active` |
| **Completion rate** | `rate(workticket_jobs_completed_total[5m])` |
| **Stuck jobs** | `workticket_stuck_jobs_total` |
| **Dashboard row** | `workticket-slos` → row "Queue Health" |
| **Alerts** | `CeleryTaskLatencyHigh`, per-queue depth alerts, `CeleryWorkerStalled`, `StuckJobsDetected` |
| **Error budget** | 7.2 hours/month allowed queue degradation |

## 8. AI Availability (95%)

| Aspect | Detail |
|--------|--------|
| **Primary metric** | `workticket_ai_fallback_total` vs `workticket_jobs_completed_total` |
| **SLI query** | `1 - (rate(workticket_ai_fallback_total[5m]) / rate(workticket_jobs_completed_total[5m]))` |
| **Circuit breaker** | `workticket_ai_gateway_llm_circuit`, `workticket_ai_gateway_whisper_circuit` |
| **Concurrency health** | `workticket_concurrency_counter_negative_total`, `workticket_concurrency_acquire_failures_total` |
| **Dashboard row** | `workticket-slos` → row "AI Pipeline" |
| **Alerts** | `AILlmCircuitOpen`, `AIWhisperCircuitOpen`, `AIFallbackResponses`, `ConcurrencyAcquireFailures`, `ConcurrencyCounterNegative` |
| **Error budget** | 36 hours/month allowed AI fallback period |

## 9. Webhook Processing (99.9%)

| Aspect | Detail |
|--------|--------|
| **Primary metric** | `workticket_billing_reconciliation_duration_ms` (summary, quantile=0.999) |
| **SLI query** | `workticket_billing_reconciliation_duration_ms{quantile="0.999"} / 1000 < 10` |
| **Processing rate** | `rate(workticket_billing_reconciliation_duration_ms_count[5m])` |
| **DLQ entries** | `workticket_dlq_entries` |
| **Drift metric** | `workticket_billing_drift_abs`, `workticket_billing_drift_pct` |
| **Dashboard row** | `workticket-slos` → row "Billing" |
| **Alerts** | `DLQEntriesGrowing`, `DeadLetterWriteFailing`, `BillingDriftHigh` |
| **Error budget** | 43.2 minutes/month allowed webhook processing failure |

## 10. Slow Query Monitoring

| Aspect | Detail |
|--------|--------|
| **Metric** | `pg_stat_statements_mean_time_seconds` |
| **>500ms query rate** | `rate(pg_stat_statements_mean_time_seconds{quantile="0.99"}[5m])` |
| **>2s alert query** | `rate(pg_stat_statements_mean_time_seconds{quantile="0.99"}[5m]) > 2` |
| **Dashboard panel** | `workticket-slos` → row "API Health" → "Slow Query Count" |
| **Logging** | PostgreSQL `log_min_duration_statement = 500` (log all queries >500ms with `auto_explain`) |

## Query Cheat Sheet

```
# Availability (fraction up)
1 - (sum(rate(workticket_http_request_duration_seconds_count{status=~"5.."}[5m])) / sum(rate(workticket_http_request_duration_seconds_count[5m])))

# P95 latency (overall)
histogram_quantile(0.95, sum(rate(workticket_http_request_duration_seconds_bucket[5m])) by (le))

# P95 latency (per endpoint class)
histogram_quantile(0.95, sum(rate(workticket_http_request_duration_seconds_bucket[5m])) by (le, endpoint_class))

# P99 latency (overall)
histogram_quantile(0.99, sum(rate(workticket_http_request_duration_seconds_bucket[5m])) by (le))

# Error rate (%)
sum(rate(workticket_http_request_duration_seconds_count{status=~"5.."}[5m])) / sum(rate(workticket_http_request_duration_seconds_count[5m])) * 100

# DB pool utilization
workticket_db_pool_utilization

# Redis memory %
redis_memory_used_bytes / redis_memory_max_bytes * 100

# Queue depth (all queues)
workticket_queue_depth

# AI non-fallback rate
1 - (rate(workticket_ai_fallback_total[5m]) / rate(workticket_jobs_completed_total[5m]))

# Webhook P999 latency (seconds)
workticket_billing_reconciliation_duration_ms{quantile="0.999"} / 1000

# Slow query rate
rate(pg_stat_statements_mean_time_seconds{quantile="0.99"}[5m])

# Latency budget (fraction below target)
sum(rate(workticket_http_request_duration_seconds_bucket{le="0.2", endpoint_class="critical"}[5m])) / sum(rate(workticket_http_request_duration_seconds_count{endpoint_class="critical"}[5m]))
```
