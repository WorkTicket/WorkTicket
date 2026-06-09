# Item 4 — Immutable Audit Logging (Architectural Design)

## Current State
- Audit logs via `AIAuditLog` model in PostgreSQL (`src/backend/app/ai/audit.py`)
- TTL-based cleanup (old logs deleted periodically)
- No immutability, no external sink, no signing

## Target Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Application  │────▶│ Audit Buffer │────▶│ Secure Log Sink  │
│ (audit.log)  │     │ (Redis list) │     │ (S3/GCS/B2)      │
└─────────────┘     └──────────────┘     └─────────────────┘
                           │                       │
                           ▼                       ▼
                    ┌──────────────┐     ┌─────────────────┐
                    │ Local Spool  │     │ WORM Bucket      │
                    │ (disk fallbk)│     │ (Object Lock)    │
                    └──────────────┘     └─────────────────┘
```

## Components

### 1. Signed Audit Event Schema
```python
@dataclass
class SignedAuditEvent:
    event_id: str           # UUID v4
    timestamp: datetime     # UTC, nanosecond precision
    source: str             # service name
    event_type: str         # "ai_request" | "billing" | "auth" | "admin"
    actor_id: str           # user or system principal
    action: str             # "process_job" | "deactivate_user" | "refund"
    resource: str           # "job:abc" | "user:xyz"
    payload_hash: str       # SHA-256 of the event payload
    signature: str          # HMAC-SHA256(event_id + timestamp + source + payload_hash)
    previous_hash: str      # SHA-256 of the previous event (blockchain chain)
```

### 2. WORM Storage (R2/S3 with Object Lock)
```python
import boto3
from botocore.config import Config

class WORMStorage:
    def __init__(self, bucket: str, retention_days: int = 365):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = bucket
        self.retention_days = retention_days

    async def store_event(self, event: SignedAuditEvent) -> str:
        key = f"audit/{event.timestamp:%Y/%m/%d}/{event.event_id}.json"
        body = json.dumps(asdict(event), default=str)
        
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ObjectLockMode="COMPLIANCE",
            ObjectLockRetainUntilDate=(
                datetime.now(timezone.utc) + timedelta(days=self.retention_days)
            ),
            ContentType="application/json",
        )
        return key
```

### 3. Audit Event Chain Verification
```python
class AuditChainVerifier:
    def verify_chain(self, events: list[SignedAuditEvent]) -> bool:
        prev_hash = ""
        for event in events:
            expected_hash = sha256(f"{event.previous_hash}{event.event_id}".encode())
            if event.previous_hash != prev_hash:
                return False
            prev_hash = expected_hash
        return True
```

### 4. Secure Log Sink (Vector/Grafana Loki)
Deploy Vector as a sidecar to batch-audit events to S3:
```yaml
# vector.toml
[sources.audit_logs]
type = "file"
include = ["/var/log/workticket/audit/*.json"]

[transforms.sign]
type = "remap"
inputs = ["audit_logs"]
source = '''
  .signature = encode_hex(hmac_sha256(.event_id + .timestamp, env("AUDIT_SIGNING_KEY")))
'''

[sinks.s3]
type = "aws_s3"
inputs = ["sign"]
bucket = "workticket-audit"
key_prefix = "audit/%%Y/%%m/%%d/"
compression = "gzip"
```

### 5. Implementation Priority
| Phase | Work | Timeline |
|---|---|---|
| P1 | Add signing to existing `AIAuditLog` model | Sprint 1 |
| P2 | Implement WORM storage sink (R2/S3) | Sprint 2 |
| P3 | Deploy Vector sidecar for batch shipping | Sprint 3 |
| P4 | Chain verification endpoint (`/admin/audit/verify`) | Sprint 4 |
| P5 | Replace PostgreSQL audit with external sink only | Sprint 5 |

### 6. Cost Estimate at Beta Scale
- 50k events/day × 1KB = 50MB/day = 1.5GB/month
- R2 storage: ~$0.015/GB/month = $0.02/month
- R2 operations: ~$0.36/10M writes = negligible
- **Total: <$1/month**

### 7. Audit Query Pattern
```python
@app.get("/admin/audit/{event_id}")
async def get_audit_event(event_id: str):
    """Fetch a signed audit event and verify its integrity."""
    # 1. Fetch from WORM storage
    # 2. Verify signature
    # 3. Verify chain linkage
    # 4. Return with verification proof
```

### 8. Key Management
- `AUDIT_SIGNING_KEY` — HMAC key for event signatures, rotated quarterly
- Stored in environment variable (same as other secrets)
- Separate key per environment (dev/staging/production)
- Canary events published hourly to detect tampering
