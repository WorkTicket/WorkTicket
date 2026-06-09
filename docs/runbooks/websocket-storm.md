# WebSocket Storm Runbook

## Detection

- Gauge `_active_websockets` approaching `MAX_WS_CONNECTIONS_GLOBAL` (default 500)
- Rate limit rejections: `workticket_ws_pubsub_fallback_total` increasing
- DB connection pool reaching capacity from WS polling fallback

## Metrics to Watch

| Metric | Threshold | Action |
|--------|-----------|--------|
| `workticket_ws_connections_total` | > 400 | Prepare to scale |
| `workticket_ws_auth_cache_size` | > 900 | Check for cache leak |
| `rate(workticket_ws_pubsub_fallback_total[5m])` | > 10 | Redis PubSub issue |

## Recovery

1. **Rate limit enforcement:** Already active via `_WS_CONNECT_RATE` (10/60s per user) and global cap (500)
2. **Connection drain:** Reduce replicas gradually (not all at once) to avoid reconnect storm
3. **Per-user connection kill:** If specific user is abusing, identify via:
   ```python
   from app.ai.router import _local_ws_connections
   # Inspect user connection counts
   ```
4. **Restart backend:** If cache corruption, restarting workers clears `_local_ws_connections` fallback state

## Prevention

- Ensure Redis is always available for WS auth caching
- Monitor `workticket_ws_auth_cache_size` — LRU eviction should keep it under 1000
- If Redis is down, WS falls to DB polling (30s interval minimum) — expect higher DB load
