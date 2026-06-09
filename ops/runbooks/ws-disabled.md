# WebSocket Disabled Runbook

## Detection
- Alert: `WsDisabled` fires when `workticket_ws_enabled == 0`
- Customer complaint: real-time job status updates not working

## Triage
1. Check WS_ENABLED env var: `docker-compose exec backend env | grep WS_ENABLED`
2. Check /readyz: `ws_enabled` component should show enabled: true
3. Check docker-compose.yml backend service environment section

## Fix
1. Set `WS_ENABLED=true` in docker-compose.yml backend environment
2. Redeploy: `docker-compose up -d backend`
3. Verify: `curl -s http://localhost:8000/readyz | jq .components.ws_enabled`

## Verification
1. Check `workticket_ws_enabled` gauge reports 1
2. Test WebSocket connection: `wscat -c ws://localhost:8000/api/v1/ai/ws/job-status/<job_id>`
3. Check /readyz returns ws_enabled status "ok"
