# Item 8 — Redis Security Configuration

## Authentication (AUTH - already partially configured)
`docker-compose.yml` already uses `--requirepass ${REDIS_PASSWORD:-changeme_in_production}`.
**Must enforce strong passwords in production.**

```bash
# Generate a strong Redis password
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## ACL Configuration (Redis 6+)
Replace `--requirepass` with ACL-based access control:

```conf
# redis-acl.conf
# Admin user (full access, for ops)
user default off
user admin on ><STRONG_ADMIN_PASSWORD> ~* &* +@all

# App user (keyspace-restricted)
user worker on ><STRONG_WORKER_PASSWORD> ~cache:* ~job:* ~ws:* -@dangerous +@all ~*

# Cache user (read-only on cache keys)
user cache on ><STRONG_CACHE_PASSWORD> ~cache:* -@all +@read +@pubsub
```

Update docker-compose.yml:
```yaml
redis-broker:
  command: ["redis-server", "/usr/local/etc/redis/redis.conf", "--aclfile", "/etc/redis/users.acl"]
  volumes:
    - ./ops/redis/redis-broker.conf:/usr/local/etc/redis/redis.conf:ro
    - ./ops/redis/users.acl:/etc/redis/users.acl:ro
```

## Private Subnet (already in place)
Both `backend-redis` and `backend-db` networks use `internal: true`.
- `redis-broker` on `backend-redis` (internal)
- `redis-cache` on `backend-redis` (internal)

## TLS Configuration
For production, enable TLS between app and Redis:

```yaml
redis-broker:
  command: [
    "redis-server",
    "--tls-port", "6380",
    "--port", "0",
    "--tls-cert-file", "/etc/redis/certs/redis.crt",
    "--tls-key-file", "/etc/redis/certs/redis.key",
    "--tls-ca-cert-file", "/etc/redis/certs/ca.crt",
    "--tls-auth-clients", "yes",
  ]
  volumes:
    - ./ops/redis/certs:/etc/redis/certs:ro
```

Update backend env vars:
```yaml
REDIS_URL: rediss://worker:<PASSWORD>@redis-cache:6380/0?ssl_cert_reqs=required
REDIS_BROKER_URL: rediss://worker:<PASSWORD>@redis-broker:6380/0?ssl_cert_reqs=required
```

## Verification
```bash
# Verify AUTH required
docker compose exec redis-broker redis-cli PING  # Should fail (NOAUTH)

# Verify ACL works
docker compose exec redis-broker redis-cli --user worker --pass <PASSWORD> PING  # Should succeed

# Verify unauthorized access blocked
docker compose exec redis-broker redis-cli --user worker --pass <PASSWORD> CONFIG GET *  # Should fail
```

## Rename Dangerous Commands
Add to redis config:
```
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command CONFIG ""
rename-command SHUTDOWN ""
rename-command DEBUG ""
rename-command SLAVEOF ""
rename-command REPLICAOF ""
rename-command SAVE ""
rename-command BGSAVE ""
rename-command BGREWRITEAOF ""
```
