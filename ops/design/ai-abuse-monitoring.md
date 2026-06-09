# Item 9 — AI Abuse Monitoring (Architectural Design)

## Current State
- Basic abuse detection via `abuse_detector.py` (risk scores, per-process spike tracking)
- No centralized monitoring dashboard
- No spend anomaly detection
- No alerting pipeline

## Target Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│ Application   │───▶│ Redis Streams │───▶│ Anomaly Detector │
│ (events)      │    │ (abuse:*)     │    │ (Python service)  │
└──────────────┘    └──────────────┘    └──────────────────┘
                          │                      │
                          ▼                      ▼
                  ┌────────────────┐    ┌──────────────────┐
                  │ PostHog/ClickH.│    │ Alert Manager     │
                  │ (analytics)    │    │ (Slack/PagerDuty) │
                  └────────────────┘    └──────────────────┘
```

## Components

### 1. Centralized Abuse Event Pipeline

Replace per-process spike tracking with Redis-backed event streams:

```python
class CentralizedAbuseMonitor:
    def __init__(self):
        self.redis = redis_client
        self.stream_key = "abuse:events"
        self.spend_key = "abuse:spend"
        self.window = 300  # 5-minute window

    async def record_event(self, company_id: str, event_type: str, metadata: dict):
        """Record an abuse-relevant event to the central stream."""
        event = {
            "company_id": company_id,
            "event_type": event_type,
            "timestamp": time.time(),
            **metadata,
        }
        await self.redis.xadd(self.stream_key, event, maxlen=10000)

    async def check_spike(self, company_id: str, threshold: int = 10) -> bool:
        """Check if company has exceeded burst threshold in the current window."""
        now = time.time()
        cutoff = now - self.window
        events = await self.redis.xrange(
            self.stream_key,
            min=int(cutoff * 1000),  # Redis stream IDs are millisecond timestamps
            max="+",
        )
        company_events = [
            e for e in events
            if e[1].get(b"company_id", b"").decode() == company_id
        ]
        return len(company_events) > threshold
```

### 2. Spend Spike Detection

```python
class SpendMonitor:
    def __init__(self):
        self.redis = redis_client
        self.daily_spend_key = "abuse:daily_spend"
        self.alert_threshold = float(os.getenv("ABUSE_SPEND_ALERT_THRESHOLD", "50.0"))  # USD

    async def track_spend(self, company_id: str, amount: float):
        daily_key = f"{self.daily_spend_key}:{company_id}:{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        new_total = await self.redis.incrbyfloat(daily_key, amount)
        await self.redis.expire(daily_key, 86400 * 2)

        if new_total > self.alert_threshold:
            await self.send_alert(company_id, new_total, "daily_spend_exceeded")

    async def send_alert(self, company_id: str, amount: float, reason: str):
        alert = {
            "company_id": company_id,
            "amount": amount,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": "high" if amount > self.alert_threshold * 3 else "medium",
        }
        await self.redis.xadd("abuse:alerts", alert)

        # Route to notification channels
        if alert["severity"] == "high":
            # PagerDuty / OpsGenie for high severity
            await self.pagerduty_alert(alert)
        else:
            # Slack notification for medium severity
            await self.slack_alert(alert)
```

### 3. Abuse Dashboard (FastAPI endpoint)

```python
@app.get("/admin/abuse/dashboard")
async def abuse_dashboard(
    minutes: int = Query(60),
    current_user: User = Depends(get_current_user),
):
    """Return abuse monitoring dashboard data."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    # Top companies by event count
    top_abusers = await abuse_monitor.get_top_companies(
        limit=10, since=cutoff
    )

    # Spend anomalies
    spend_anomalies = await spend_monitor.get_anomalies(
        since=cutoff, threshold=50.0
    )

    # Active alerts
    active_alerts = await abuse_monitor.get_active_alerts()

    return {
        "time_window_minutes": minutes,
        "total_events": await abuse_monitor.get_event_count(since=cutoff),
        "top_abusers": top_abusers,
        "spend_anomalies": spend_anomalies,
        "active_alerts": active_alerts,
        "rate_limiter_status": {
            "redis_available": rate_limiter.redis_available,
            "fallback_active": rate_limiter.fallback_active,
            "local_workers": rate_limiter._ESTIMATED_WORKERS,
        },
    }
```

### 4. Alert Routing Configuration (`ops/alert-routing.yml`)

```yaml
alerts:
  spend_spike:
    condition: daily_spend > $50
    channels:
      - slack:#billing-alerts
      - email:billing@workticket.com
    severity: medium
    cooldown: 6h

  burst_detected:
    condition: requests_per_5min > 100
    channels:
      - slack:#abuse-alerts
      - pagerduty:abuse
    severity: high
    cooldown: 15min

  concurrent_limit_hit:
    condition: company_concurrency_rejected > 0
    channels:
      - slack:#ops-alerts
    severity: low
    cooldown: 1h
```

### 5. Prometheus Metrics Integration
```python
# metrics.py additions
ABUSE_EVENTS = Counter(
    "workticket_abuse_events_total",
    "Total abuse-related events",
    ["company_id", "event_type"],
)

SPEND_ALERTS = Counter(
    "workticket_spend_alerts_total",
    "Total spend alerts triggered",
    ["severity"],
)

COMPANY_RISK_SCORE = Gauge(
    "workticket_company_risk_score",
    "Current risk score per company",
    ["company_id"],
)
```

### 6. Implementation Priority
| Phase | Work | Timeline |
|---|---|---|
| P1 | Migrate abuse spike tracking from per-process to Redis | Sprint 1 |
| P2 | Implement spend anomaly detection | Sprint 1 |
| P3 | Create abuse dashboard endpoint | Sprint 2 |
| P4 | Integrate Prometheus metrics | Sprint 2 |
| P5 | Alert routing (Slack/PagerDuty) | Sprint 3 |
| P6 | ML-based anomaly detection (optional) | Future |
