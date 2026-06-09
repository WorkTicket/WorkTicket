"""RELEASE GATE C — Production Launch Certification (Go / No-Go).

This is NOT a normal test file. It is a deployment certification system.
Every item is a blocker. Zero exceptions. Zero "we'll fix it later."

RUN AUTOMATED CHECKS (no database required):
    python tests/release_gates/gate_c_production_launch_checklist.py

PRINCIPLE:
    ALL 8 SECTIONS MUST PASS → GO FOR LAUNCH
    ANY FAIL → NO-GO, FIX BEFORE DEPLOYMENT
"""

import os
import sys

# ============================================================================
# SECTION 1 — DATA INTEGRITY CHECKS
# ============================================================================

GATE_C1_DATA_INTEGRITY = """
## GATE C1 — DATA INTEGRITY CERTIFICATION

### 1.1 Import Log Audit Trail
   [ ] All import_logs rows have non-null external_system AND external_id
   [ ] Zero import_logs with result='success' AND internal_id=NULL
   [ ] import_logs table has uq_import_logs_dedup constraint enforced
   EVIDENCE: SELECT count(*) FROM import_logs WHERE external_system IS NULL OR external_id IS NULL; => 0

### 1.2 Deduplication Proof
   [ ] Gate A2 passed (double-run = 0 duplicates)
   [ ] Gate B3 passed (live data imported without duplicates)
   [ ] Zero import_logs with same (company_id, external_system, external_id, entity_type)
   EVIDENCE: pytest tests/release_gates/gate_a_integration_migration_test.py::TestGateA2_DeduplicationIntegrity -v

### 1.3 External ID Preservation
   [ ] Every imported entity traceable back to source system
   [ ] No external_id truncation (verify against max source system ID length)
   EVIDENCE: Sample 100 import_logs rows, verify each external_id matches source system format.

### 1.4 Tenant Isolation Verified
   [ ] Gate A4 passed
   [ ] RLS policies enabled on all 4 integration tables
   [ ] Cross-tenant queries return zero rows
   EVIDENCE: pytest tests/release_gates/gate_a_integration_migration_test.py::TestGateA4_TenantIsolation -v

VERDICT C1: [ ] PASS / [ ] FAIL
"""

# ============================================================================
# SECTION 2 — SECURITY CERTIFICATION
# ============================================================================

GATE_C2_SECURITY = """
## GATE C2 — SECURITY CERTIFICATION

### 2.1 Token Encryption at Rest
   [ ] integration_connections.access_token uses EncryptedString type
   [ ] integration_connections.refresh_token uses EncryptedString type
   [ ] Tokens not visible in plaintext in database (verify via SELECT)
   EVIDENCE: SELECT access_token FROM integration_connections LIMIT 1; => starts with 'v1:'

### 2.2 No Token Exposure in Logs
   [ ] Access tokens never logged (check app logs, Sentry, CloudWatch)
   [ ] Refresh tokens never logged
   EVIDENCE: grep -r "sk_live\\|sk_test\\|Bearer" /var/log/app/*.log => 0 results (except auth headers)

### 2.3 API Authentication Enforced
   [ ] All integration endpoints require valid auth (test without token => 401)
   [ ] RBAC enforcement on integration routes (technician cannot access)
   EVIDENCE: curl /api/v1/integrations/connections without Authorization => 401

### 2.4 Rate Limiting on Integration Endpoints
   [ ] Scan endpoints rate-limited (prevent API abuse against providers)
   [ ] Import endpoints rate-limited
   EVIDENCE: 20 rapid scan requests => at least some get 429

VERDICT C2: [ ] PASS / [ ] FAIL
"""

# ============================================================================
# SECTION 3 — PERFORMANCE CERTIFICATION
# ============================================================================

GATE_C3_PERFORMANCE = """
## GATE C3 — PERFORMANCE CERTIFICATION

### 3.1 Import Throughput Benchmarks
   [ ] 1,000 customer import completes in < 60 seconds
   [ ] 10,000 record import completes in < 5 minutes
   [ ] No OOM events during 25,000 record import
   [ ] Database connection pool never exhausted during import
   EVIDENCE: Run benchmark_import.py with 1k/10k/25k records, capture timing + memory.

### 3.2 API Latency Under Load
   [ ] Provider list endpoint: p99 < 200ms
   [ ] Connection health endpoint: p99 < 500ms
   [ ] Import status endpoint: p99 < 300ms
   EVIDENCE: k6/vegeta load test at 50 concurrent users.

### 3.3 Background Worker Stability
   [ ] Import survives worker restart (import resumes or marks as failed cleanly)
   [ ] Import survives Redis restart (no data corruption)
   [ ] No stuck import jobs after 24 hours
   EVIDENCE: chaos/redis_failover.py run during import, verify import_jobs status is not in_progress after 1h.

### 3.4 Batch Processing Memory Profile
   [ ] Memory usage flat during 50k record import (no linear growth)
   [ ] Batch flushes prevent transaction log bloat
   EVIDENCE: Monitor RSS during import, verify < 500MB baseline + 200MB per import.

VERDICT C3: [ ] PASS / [ ] FAIL
"""

# ============================================================================
# SECTION 4 — RELIABILITY CERTIFICATION
# ============================================================================

GATE_C4_RELIABILITY = """
## GATE C4 — RELIABILITY CERTIFICATION

### 4.1 Connection Health Monitoring Operational
   [ ] Health endpoint returns accurate status for each provider
   [ ] Token expiry detection works (TOKEN_EXPIRING when < 7 days)
   [ ] Rate limit detection triggers RATE_LIMITED status
   EVIDENCE: Gate A7 + Gate B1 health tests pass.

### 4.2 Failure Recovery Paths Verified
   [ ] Invalid token => clear error, no partial import, no crash
   [ ] Expired token => ERROR status, not silent failure
   [ ] Provider API down => import job marked FAILED, not hung
   EVIDENCE: Gate B4 tests pass against real sandbox.

### 4.3 Partial Failure Handling
   [ ] Gate A8 passed (import continues on individual failures)
   [ ] Import reports PARTIAL status accurately
   [ ] Failed records logged with error_message
   EVIDENCE: pytest tests/release_gates/gate_a_integration_migration_test.py::TestGateA8_PartialFailureResilience -v

### 4.4 Idempotency Guaranteed
   [ ] Unique constraint on import_logs (company_id, external_system, external_id, entity_type)
   [ ] already_imported() check before every insert
   [ ] Re-running import produces zero new records (Gate A6 dry run validation)
   EVIDENCE: Double-run import test, verify imported=0 on second run.

VERDICT C4: [ ] PASS / [ ] FAIL
"""

# ============================================================================
# SECTION 5 — PROVIDER CERTIFICATION
# ============================================================================

GATE_C5_PROVIDER_CERTIFICATION = """
## GATE C5 — PROVIDER CERTIFICATION

### 5.1 Stripe (PAYMENTS)
   [ ] Gate B: Stripe auth works (test mode)
   [ ] Gate B: Stripe customer pagination validated
   [ ] Gate B: Stripe dry run accuracy confirmed
   [ ] Customers imported with external_id = 'cus_...'
   [ ] Invoices imported with external_id = 'in_...'
   [ ] Payments imported with external_id = 'pi_...'
   EVIDENCE: pytest tests/release_gates/gate_b_live_sandbox_validation.py -v -k stripe -m sandbox

### 5.2 QuickBooks Online (ACCOUNTING)
   [ ] Gate B: QBO sandbox auth works
   [ ] Gate B: QBO company info accessible
   [ ] Customers imported with external_id from Intuit
   [ ] Invoices imported with DocNumber preserved
   [ ] OAuth token refresh flow tested
   EVIDENCE: pytest tests/release_gates/gate_b_live_sandbox_validation.py -v -k quickbooks -m sandbox

### 5.3 At Least ONE Field Service System
   [ ] Jobber OR Housecall Pro sandbox auth works
   [ ] Jobs/customers import successfully
   [ ] Schedule events import successfully
   EVIDENCE: Gate B tests for jobber or housecall_pro pass.

### 5.4 CSV Import Engine (UNIVERSAL FALLBACK)
   [ ] Gate A5: All CSV edge cases handled
   [ ] UTF-8 with BOM works
   [ ] Missing columns handled gracefully
   [ ] Custom column mapping works end-to-end
   EVIDENCE: pytest tests/release_gates/gate_a_integration_migration_test.py::TestGateA5_CSVImportStress -v

VERDICT C5: [ ] PASS / [ ] FAIL
"""

# ============================================================================
# SECTION 6 — OPERATIONAL CERTIFICATION
# ============================================================================

GATE_C6_OPERATIONAL = """
## GATE C6 — OPERATIONAL READINESS

### 6.1 Database Migration Verified
   [ ] Alembic migration 039 applied cleanly to staging
   [ ] Alembic migration 039 downgrade tested (rollback works)
   [ ] No orphaned tables or missing indexes
   EVIDENCE: alembic upgrade head && alembic downgrade -1 && alembic upgrade head

### 6.2 Monitoring & Alerting Configured
   [ ] Prometheus metrics for import job duration
   [ ] Alert if import job stuck IN_PROGRESS > 1 hour
   [ ] Alert if connection health degraded
   [ ] Dashboard showing active imports, recent failures, provider status
   EVIDENCE: Screenshot of Grafana dashboard showing import metrics.

### 6.3 Logging & Debugging
   [ ] Import start/complete logged at INFO level
   [ ] Import errors logged at ERROR level with stack traces
   [ ] External IDs included in log messages for traceability
   EVIDENCE: Sample log output from a test import run.

### 6.4 Backup & Recovery
   [ ] import_logs included in database backup schedule
   [ ] integration_connections tokens backed up (encrypted)
   [ ] Recovery plan documented for lost connection state
   EVIDENCE: Backup script includes integration tables.

VERDICT C6: [ ] PASS / [ ] FAIL
"""

# ============================================================================
# SECTION 7 — UX CERTIFICATION
# ============================================================================

GATE_C7_UX = """
## GATE C7 — USER EXPERIENCE CERTIFICATION

### 7.1 Import Wizard Flow
   [ ] Settings > Integrations page loads with provider list
   [ ] Provider status correctly displayed (production/beta/stub)
   [ ] Connect flow guides user through OAuth/API key entry
   [ ] Scan results display record counts per entity type
   EVIDENCE: Manual walkthrough or E2E test recording.

### 7.2 Import Progress UX
   [ ] Progress percentage updates during import
   [ ] Import completion shows imported/skipped/failed counts
   [ ] Errors displayed with actionable messages (not raw stack traces)
   EVIDENCE: Manual walkthrough of import flow.

### 7.3 Error Messaging
   [ ] Invalid credentials => "Connection failed: please re-authenticate"
   [ ] Rate limited => "Provider is busy, your import will resume automatically"
   [ ] Import failure => "X records imported, Y failed. View details"
   EVIDENCE: Review error response format for each failure mode.

### 7.4 CSV Import UX
   [ ] File upload accepts .csv files
   [ ] Preview shows first 10 rows with auto-mapped columns
   [ ] User can adjust column mapping before import
   [ ] Import results show parsed/skipped/failed counts
   EVIDENCE: Manual walkthrough of CSV import flow.

VERDICT C7: [ ] PASS / [ ] FAIL
"""

# ============================================================================
# SECTION 8 — AUTOMATED CODE CHECKS
# ============================================================================

def _check(msg: str, passed: bool):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} {msg}")
    return passed


def run_automated_checks() -> bool:
    """Run programmatic checks that validate code structure without a database."""
    print("=" * 60)
    print("RELEASE GATE C8 — AUTOMATED CODE VERIFICATION")
    print("=" * 60)
    all_passed = True

    # C8.1: Tenant isolation table coverage
    try:
        from app.database import _TENANT_SCOPED_TABLES
        required = {"integration_connections", "import_jobs", "import_logs", "mapping_rules"}
        missing = required - _TENANT_SCOPED_TABLES
        ok = len(missing) == 0
        if not ok:
            print(f"  MISSING: {missing}")
        all_passed &= _check("Integration tables in tenant isolation", ok)
    except Exception as e:
        all_passed &= _check(f"Tenant isolation check: {e}", False)

    # C8.2: Router registered
    try:
        from app.main import app
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        integration_routes = [r for r in routes if "/integrations" in r]
        all_passed &= _check(f"Integrations router registered ({len(integration_routes)} routes)", len(integration_routes) > 0)
    except Exception as e:
        all_passed &= _check(f"Router check: {e}", False)

    # C8.3: EncryptedString on access_token
    try:
        from app.db.encrypted_string import EncryptedString
        from app.integrations.models import IntegrationConnection
        col = IntegrationConnection.__table__.columns.get("access_token")
        ok = col is not None and isinstance(col.type, EncryptedString)
        all_passed &= _check("access_token uses EncryptedString", ok)
    except Exception as e:
        all_passed &= _check(f"EncryptedString check: {e}", False)

    # C8.4: EncryptedString on refresh_token
    try:
        from app.db.encrypted_string import EncryptedString
        from app.integrations.models import IntegrationConnection
        col = IntegrationConnection.__table__.columns.get("refresh_token")
        ok = col is not None and isinstance(col.type, EncryptedString)
        all_passed &= _check("refresh_token uses EncryptedString", ok)
    except Exception as e:
        all_passed &= _check(f"EncryptedString check: {e}", False)

    # C8.5: Unique constraint on import_logs
    try:
        from app.integrations.models import ImportLog
        constraints = [c.name for c in ImportLog.__table__.constraints if hasattr(c, "name")]
        ok = "uq_import_logs_dedup" in constraints
        all_passed &= _check("uq_import_logs_dedup constraint exists", ok)
    except Exception as e:
        all_passed &= _check(f"Constraint check: {e}", False)

    # C8.6: Migration file exists
    migration_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "alembic", "versions", "039_add_integration_tables.py"
    )
    all_passed &= _check("Alembic migration 039 exists", os.path.exists(migration_path))

    # C8.7: Minimum providers registered
    try:
        from app.integrations.registry import PROVIDERS
        required_providers = {"quickbooks", "jobber", "housecall_pro", "stripe"}
        missing_providers = required_providers - set(PROVIDERS.keys())
        ok = len(missing_providers) == 0
        if not ok:
            print(f"  MISSING: {missing_providers}")
        all_passed &= _check("4 MVP providers in registry", ok)
    except Exception as e:
        all_passed &= _check(f"Registry check: {e}", False)

    # C8.8: No plaintext secrets in code
    try:
        import ast
        models_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "app", "integrations", "models.py")
        with open(models_path) as f:
            tree = ast.parse(f.read())
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith(("sk_live_", "sk_test_")) and len(node.value) > 20:
                found = True
                break
        all_passed &= _check("No hardcoded secrets in models.py", not found)
    except Exception as e:
        all_passed &= _check(f"Secrets check: {e}", False)

    # C8.9: Feature flags operational
    try:
        from app.integrations.feature_flags import integration_flags
        integration_flags.enable("__gate_c_test__")
        flag = integration_flags.get_flag("__gate_c_test__")
        integration_flags.disable("__gate_c_test__")
        all_passed &= _check("Feature flags module operational", flag.value == "enabled")
    except Exception as e:
        all_passed &= _check(f"Feature flags check: {e}", False)

    # C8.10: BaseConnector contract completeness
    try:
        from app.integrations.connectors.base import BaseConnector
        required_methods = [
            "authenticate", "fetch_customers", "fetch_jobs", "fetch_work_orders",
            "fetch_invoices", "fetch_payments", "fetch_employees", "fetch_assets",
            "fetch_schedule_events", "sync_all",
        ]
        missing_methods = []
        for method in required_methods:
            if not hasattr(BaseConnector, method) or getattr(BaseConnector, method) is None:
                missing_methods.append(method)
        ok = len(missing_methods) == 0
        if not ok:
            print(f"  MISSING: {missing_methods}")
        all_passed &= _check("BaseConnector contract complete (10 methods)", ok)
    except Exception as e:
        all_passed &= _check(f"Contract check: {e}", False)

    print("=" * 60)
    if all_passed:
        print("C8 AUTOMATED: ALL CHECKS PASSED")
    else:
        print("C8 AUTOMATED: SOME CHECKS FAILED — LAUNCH BLOCKED")
    print("=" * 60)
    return all_passed


GATE_C_FINAL = """
============================================================
        PRODUCTION LAUNCH CERTIFICATION — GATE C
============================================================
  C1 Data Integrity      [ ] PASS / [ ] FAIL
  C2 Security            [ ] PASS / [ ] FAIL
  C3 Performance         [ ] PASS / [ ] FAIL
  C4 Reliability         [ ] PASS / [ ] FAIL
  C5 Provider Cert       [ ] PASS / [ ] FAIL
  C6 Operational         [ ] PASS / [ ] FAIL
  C7 UX                  [ ] PASS / [ ] FAIL
  C8 Automated Checks    [ ] PASS / [ ] FAIL
============================================================

  ALL 8 GATES MUST PASS => GO FOR LAUNCH
  ANY GATE FAILS => NO-GO, FIX BEFORE LAUNCH

  Certified by: _____________________  Date: _______________
============================================================
"""

if __name__ == "__main__":
    print("RELEASE GATE C — PRODUCTION LAUNCH CERTIFICATION")
    print(GATE_C1_DATA_INTEGRITY)
    print(GATE_C2_SECURITY)
    print(GATE_C3_PERFORMANCE)
    print(GATE_C4_RELIABILITY)
    print(GATE_C5_PROVIDER_CERTIFICATION)
    print(GATE_C6_OPERATIONAL)
    print(GATE_C7_UX)
    print()
    c8_passed = run_automated_checks()
    print()
    print(GATE_C_FINAL)
    sys.exit(0 if c8_passed else 1)
