# Redis Outage Runbook

## Symptoms
- `workticket_rate_limiter_redis_available == 0`
- `ConcurrencyLockFallbackActive` alert
- Rate limiter, WebSocket tracking, and concurrency locks using local fallback
- `/readyz` shows `redis: failed`

## System Behavior During Outage
- **Rate limiter**: Falls back to in-process local counters (approximate per-replica limits)
- **Concurrency locks**: Falls back to local in-process tracking
- **WebSocket connection tracking**: Falls back to local per-process limits
- **WebSocket pub/sub**: Degraded — polls DB instead
- **Celery broker**: If Redis is the broker too, tasks cannot be dispatched or consumed
- **All services remain functional** for already-dispatched tasks

## Steps

### 1. Diagnose
```bash
redis-cli -h <host> -p <port> ping
redis-cli -h <host> -p <port> info stats | grep -E "(connected_clients|used_memory|evicted_keys)"
```

### 2. Restart Redis (if needed)
```bash
docker-compose restart redis-cache
docker-compose restart redis-broker
```

Or for HA setup with Sentinel:
```bash
# Identify current master
redis-cli -p 26379 SENTINEL get-master-addr-by-name workticket
# Failover if needed
redis-cli -p 26379 SENTINEL failover workticket
```

### 3. Verify queue integrity after restart
```bash
redis-cli -h <host> -p <port> LLEN default
redis-cli -h <host> -p <port> LLEN ai_text
redis-cli -h <host> -p <port> LLEN ai_audio
redis-cli -h <host> -p <port> LLEN ai_image
```

### 4. Verify recovery
- Rate limiter shows `mode: redis` in `/readyz`
- Concurrency locks re-acquire via Redis
- WebSocket tracking works globally

## Prevention
- Use Redis Sentinel for HA failover
- Set `maxmemory-policy noeviction` to prevent key eviction
- Monitor memory usage and scale Redis instance size proactively
