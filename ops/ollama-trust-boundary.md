# Item 7 — Ollama Trust Boundary Configuration

## Localhost-Only Bind
Update `docker-compose.yml` ollama service to bind only to localhost:

```yaml
ollama:
  ports:
    - "127.0.0.1:11434:11434"  # localhost-only, not 0.0.0.0
```

## Docker Network Isolation (already in place)
Ollama is on the `ai-internal` network which uses `internal: true`:
- No external access to Ollama from outside Docker
- Only backend, celery-worker-*, and whisper-service can reach Ollama
- Verified in docker-compose.yml lines 339-341

## Firewall Rules (host-level)
```bash
# On the Docker host, restrict port 11434 to localhost only
iptables -A INPUT -p tcp --dport 11434 ! -i lo -j DROP
# Or with ufw
ufw deny in on any to any port 11434
```

## Verify Setup
```bash
# From outside the ai-internal network — should fail
curl http://ollama:11434/api/tags  # Should timeout or connection refused

# From inside ai-internal — should work
docker compose exec backend curl -sf http://ollama:11434/api/tags
```

## Additional Hardening
1. Remove `ports` mapping entirely from ollama service — backend always connects via Docker DNS
2. Use read-only root filesystem for ollama container
3. Set `OLLAMA_HOST=127.0.0.1` inside container to prevent accidental external bind
4. Monitor `ai-internal` network traffic for anomalies
