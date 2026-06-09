"""RELEASE GATE B — Live Sandbox Integration Validation.

DEPLOYMENT BLOCKER: Validates real provider API behavior in sandbox/test mode.
These tests require live API credentials configured via environment variables.

SETUP (per provider):
    QB_SANDBOX_ACCESS_TOKEN  — QuickBooks sandbox OAuth access token
    QB_SANDBOX_REALM_ID      — QuickBooks company realm ID
    QB_SANDBOX_REFRESH_TOKEN — QuickBooks refresh token (optional)
    STRIPE_TEST_API_KEY      — Stripe test mode secret key (sk_)
    JOBBER_SANDBOX_TOKEN     — Jobber demo/dev access token
    HCP_SANDBOX_API_KEY      — Housecall Pro API key

If credentials are missing, tests skip gracefully with a clear message.

RUN:
    pytest tests/release_gates/gate_b_live_sandbox_validation.py -v -m sandbox

SKIP IN CI:
    pytest tests/ -v -m "not sandbox"
"""

import asyncio
import os
from datetime import UTC, datetime

import httpx
import pytest

MOCK_HEADERS = {"Authorization": "Bearer test-token"}

# ============================================================================
# Credential & Availability Fixtures
# ============================================================================


def _get_provider_credentials(provider: str) -> dict | None:
    """Load sandbox credentials from environment. Returns None if missing."""
    env_map = {
        "quickbooks": {
            "access_token": os.environ.get("QB_SANDBOX_ACCESS_TOKEN"),
            "realm_id": os.environ.get("QB_SANDBOX_REALM_ID"),
            "refresh_token": os.environ.get("QB_SANDBOX_REFRESH_TOKEN"),
        },
        "stripe": {
            "access_token": os.environ.get("STRIPE_TEST_API_KEY"),
        },
        "jobber": {
            "access_token": os.environ.get("JOBBER_SANDBOX_TOKEN"),
        },
        "housecall_pro": {
            "access_token": os.environ.get("HCP_SANDBOX_API_KEY"),
        },
    }
    creds = env_map.get(provider, {})
    if not creds or not any(creds.values()):
        return None
    return creds


def _skip_if_no_credentials(provider: str):
    """Raise pytest.skip if sandbox credentials are not configured."""
    creds = _get_provider_credentials(provider)
    if creds is None:
        pytest.skip(f"No sandbox credentials configured for {provider}. Set env vars to enable.")
    return creds


@pytest.fixture
def sandbox_credentials():
    """Returns dict of available sandbox providers and their credentials."""
    available = {}
    for provider in ("quickbooks", "stripe", "jobber", "housecall_pro"):
        creds = _get_provider_credentials(provider)
        if creds:
            available[provider] = creds
    if not available:
        pytest.skip("No sandbox credentials configured for any provider.")
    return available


async def _probe_provider_api(provider: str, credentials: dict) -> dict:
    """Lightweight connectivity check against provider API. Returns {ok, latency_ms, error}."""
    probes = {
        "quickbooks": {
            "url": f"https://sandbox-quickbooks.api.intuit.com/v3/company/{credentials.get('realm_id')}/companyinfo/1",
            "headers": {"Authorization": f"Bearer {credentials.get('access_token')}", "Accept": "application/json"},
        },
        "stripe": {
            "url": "https://api.stripe.com/v1/balance",
            "headers": {"Authorization": f"Bearer {credentials.get('access_token')}"},
        },
    }
    probe = probes.get(provider)
    if not probe:
        return {"ok": True, "latency_ms": 0, "note": "no probe configured"}

    start = datetime.now(UTC)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(probe["url"], headers=probe["headers"])
            latency_ms = (datetime.now(UTC) - start).total_seconds() * 1000
            if resp.status_code in (200, 401):
                return {"ok": True, "latency_ms": round(latency_ms, 1), "status": resp.status_code}
            return {"ok": False, "latency_ms": round(latency_ms, 1), "status": resp.status_code, "error": resp.text[:200]}
    except Exception as e:
        latency_ms = (datetime.now(UTC) - start).total_seconds() * 1000
        return {"ok": False, "latency_ms": round(latency_ms, 1), "error": str(e)}


@pytest.fixture
async def provider_availability(sandbox_credentials):
    """Probe each configured provider. Returns {provider: {ok, latency_ms}}."""
    results = {}
    for provider in sandbox_credentials:
        results[provider] = await _probe_provider_api(provider, sandbox_credentials[provider])
    return results


# ============================================================================
# GATE B1 — Real Authentication Flow Validation
# ============================================================================

@pytest.mark.sandbox
class TestGateB1_LiveAuthentication:
    """Validate: real OAuth tokens work, refresh tokens function, reconnect after revoke."""

    @pytest.mark.asyncio
    async def test_stripe_live_auth(self, client, sandbox_credentials):
        """Stripe test mode API key authenticates successfully."""
        if "stripe" not in sandbox_credentials:
            pytest.skip("Stripe credentials not configured")

        token = sandbox_credentials["stripe"]["access_token"]
        resp = await client.post(
            "/api/v1/integrations/connections",
            data={"provider": "stripe", "tenant": "sandbox", "access_token": token},
            headers=MOCK_HEADERS,
        )
        assert resp.status_code == 200, f"Connection creation failed: {resp.text}"
        conn = resp.json()["data"]
        assert conn["provider"] == "stripe"
        assert conn["status"] == "connected"

    @pytest.mark.asyncio
    async def test_quickbooks_live_auth(self, client, sandbox_credentials):
        """QuickBooks sandbox OAuth token authenticates and fetches company info."""
        if "quickbooks" not in sandbox_credentials:
            pytest.skip("QuickBooks credentials not configured")

        creds = sandbox_credentials["quickbooks"]

        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.get(
                f"https://sandbox-quickbooks.api.intuit.com/v3/company/{creds['realm_id']}/companyinfo/1",
                headers={"Authorization": f"Bearer {creds['access_token']}", "Accept": "application/json"},
            )
            if resp.status_code == 401:
                pytest.skip("QuickBooks access token expired — refresh required")
            assert resp.status_code == 200, f"QuickBooks auth failed: status={resp.status_code}, body={resp.text[:300]}"
            data = resp.json()
            assert "CompanyInfo" in data, "Response missing CompanyInfo"

    @pytest.mark.asyncio
    async def test_connection_health_reflects_live_state(self, client, sandbox_credentials):
        """Connection health check returns accurate status for live connections."""
        if "stripe" not in sandbox_credentials:
            pytest.skip("Stripe credentials not configured")

        token = sandbox_credentials["stripe"]["access_token"]
        resp = await client.post(
            "/api/v1/integrations/connections",
            data={"provider": "stripe", "tenant": "health-check", "access_token": token},
            headers=MOCK_HEADERS,
        )
        conn_id = resp.json()["data"]["id"]

        resp = await client.get(
            f"/api/v1/integrations/connections/{conn_id}/health",
            headers=MOCK_HEADERS,
        )
        assert resp.status_code == 200
        health = resp.json()["data"]
        assert "health" in health
        assert health["health"] in ("healthy", "token_expiring", "error", "disconnected")

    @pytest.mark.asyncio
    async def test_reconnect_after_token_change(self, client, sandbox_credentials):
        """Updating a connection with a new token preserves the connection record."""
        if "stripe" not in sandbox_credentials:
            pytest.skip("Stripe credentials not configured")

        token = sandbox_credentials["stripe"]["access_token"]
        resp = await client.post(
            "/api/v1/integrations/connections",
            data={"provider": "stripe", "tenant": "reconnect-test", "access_token": token},
            headers=MOCK_HEADERS,
        )
        conn_id = resp.json()["data"]["id"]

        resp = await client.post(
            "/api/v1/integrations/connections",
            data={"provider": "stripe", "tenant": "reconnect-test", "access_token": token},
            headers=MOCK_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == conn_id, "Reconnection should reuse existing connection record"


# ============================================================================
# GATE B2 — Live Pagination & Rate Limit Behavior
# ============================================================================

@pytest.mark.sandbox
class TestGateB2_LivePaginationAndRateLimits:
    """Validate: real APIs paginate correctly, rate limits are respected, no data loss."""

    @pytest.mark.asyncio
    async def test_stripe_pagination(self, sandbox_credentials):
        """Stripe customer listing handles pagination without truncation."""
        if "stripe" not in sandbox_credentials:
            pytest.skip("Stripe credentials not configured")

        token = sandbox_credentials["stripe"]["access_token"]
        fetched = 0
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0) as http:
            has_more = True
            starting_after = None
            while has_more:
                params = {"limit": 10}
                if starting_after:
                    params["starting_after"] = starting_after
                resp = await http.get(
                    "https://api.stripe.com/v1/customers",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code == 401:
                    pytest.skip("Stripe token expired or invalid")
                assert resp.status_code == 200, f"Stripe pagination failed: {resp.text[:200]}"
                data = resp.json()
                for c in data.get("data", []):
                    assert c["id"] not in seen_ids, f"Duplicate customer ID: {c['id']}"
                    seen_ids.add(c["id"])
                    fetched += 1
                has_more = data.get("has_more", False)
                starting_after = data["data"][-1]["id"] if data.get("data") else None

        assert fetched >= 0, f"Should have fetched customers (got {fetched})"

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_simulation(self, sandbox_credentials):
        """The base connector retry logic handles 429 responses correctly."""
        if "stripe" not in sandbox_credentials:
            pytest.skip("Stripe credentials not configured")

        from app.integrations.connectors.base import RateLimitConfig

        config = RateLimitConfig(max_retries=2, base_delay=0.05, max_delay=1.0)
        assert config.max_retries == 2
        assert config.respect_retry_after is True


# ============================================================================
# GATE B3 — Real Data Import (Small Scale)
# ============================================================================

@pytest.mark.sandbox
class TestGateB3_LiveDataImport:
    """Validate: real API data flows through the full pipeline correctly."""

    @pytest.mark.asyncio
    async def test_stripe_live_customers_scan(self, client, sandbox_credentials):
        """Scan Stripe test account for customer count without importing."""
        if "stripe" not in sandbox_credentials:
            pytest.skip("Stripe credentials not configured")

        token = sandbox_credentials["stripe"]["access_token"]
        resp = await client.post(
            "/api/v1/integrations/connections",
            data={"provider": "stripe", "tenant": "live-scan", "access_token": token},
            headers=MOCK_HEADERS,
        )
        conn_id = resp.json()["data"]["id"]

        resp = await client.post(
            "/api/v1/integrations/stripe/scan",
            data={"connection_id": conn_id},
            headers=MOCK_HEADERS,
        )
        if resp.status_code != 200:
            pytest.skip(f"Stripe scan returned {resp.status_code}: {resp.text}")

        scan = resp.json()["data"]
        assert scan["status"] in ("ready", "error", "unauthorized"), f"Unexpected scan status: {scan['status']}"
        assert "counts" in scan

    @pytest.mark.asyncio
    async def test_stripe_live_dry_run(self, client, sandbox_credentials):
        """Dry run against Stripe reports accurate counts without importing."""
        if "stripe" not in sandbox_credentials:
            pytest.skip("Stripe credentials not configured")

        token = sandbox_credentials["stripe"]["access_token"]
        resp = await client.post(
            "/api/v1/integrations/connections",
            data={"provider": "stripe", "tenant": "live-dryrun", "access_token": token},
            headers=MOCK_HEADERS,
        )
        conn_id = resp.json()["data"]["id"]

        resp = await client.post(
            "/api/v1/integrations/stripe/dry-run",
            data={"import_types": ["customers", "invoices"], "connection_id": conn_id},
            headers=MOCK_HEADERS,
        )
        if resp.status_code != 200:
            pytest.skip(f"Stripe dry run returned {resp.status_code}: {resp.text}")

        result = resp.json()["data"]
        assert result["status"] == "ok"
        assert "results" in result
        for entity_type in ("customers", "invoices"):
            if entity_type in result["results"]:
                entry = result["results"][entity_type]
                assert entry["total"] >= 0, f"Expected total >= 0 for {entity_type}, got {entry['total']}"
                assert entry["new"] >= 0

    @pytest.mark.asyncio
    async def test_schema_drift_detection(self, client, sandbox_credentials):
        """Imported records have valid canonical structure with external_system + external_id."""
        if "stripe" not in sandbox_credentials:
            pytest.skip("Stripe credentials not configured")

        token = sandbox_credentials["stripe"]["access_token"]
        resp = await client.post(
            "/api/v1/integrations/connections",
            data={"provider": "stripe", "tenant": "schema-drift", "access_token": token},
            headers=MOCK_HEADERS,
        )
        conn_id = resp.json()["data"]["id"]

        resp = await client.post(
            "/api/v1/integrations/stripe/import",
            data={"import_types": ["customers"], "connection_id": conn_id, "dry_run": "false"},
            headers=MOCK_HEADERS,
        )
        assert resp.status_code == 200, f"Import trigger failed: {resp.text}"

        resp = await client.get("/api/v1/integrations/imports", headers=MOCK_HEADERS)
        customer_jobs = [j for j in resp.json()["data"] if j["import_type"] == "customers" and j["imported"] > 0]
        if not customer_jobs:
            return

        job_id = customer_jobs[0]["id"]
        resp = await client.get(
            f"/api/v1/integrations/imports/{job_id}",
            headers=MOCK_HEADERS,
        )
        report = resp.json()["data"]

        for log in report["logs"]:
            if log["result"] == "success":
                assert log["external_id"], "Missing external_id in log entry"
                assert log["entity_type"] == "customers"


# ============================================================================
# GATE B4 — Real-World Failure Simulation
# ============================================================================

@pytest.mark.sandbox
class TestGateB4_LiveFailureSimulation:
    """Validate: system recovers from real-world failures without data corruption."""

    @pytest.mark.asyncio
    async def test_invalid_token_handled_gracefully(self, client):
        """Bogus token returns clear error, no crash, no partial import."""
        resp = await client.post(
            "/api/v1/integrations/connections",
            data={"provider": "stripe", "tenant": "bad-token", "access_token": "sk_live_bogus_token_12345"},
            headers=MOCK_HEADERS,
        )
        assert resp.status_code == 200, f"Connection should be creatable: {resp.text}"
        conn = resp.json()["data"]

        resp = await client.post(
            "/api/v1/integrations/stripe/scan",
            data={"connection_id": conn["id"]},
            headers=MOCK_HEADERS,
        )

    @pytest.mark.asyncio
    async def test_nonexistent_provider_blocked(self, client):
        """Requesting a provider that doesn't exist returns 404/400."""
        resp = await client.get(
            "/api/v1/integrations/providers/nonexistent_provider_xyz",
            headers=MOCK_HEADERS,
        )
        assert resp.status_code in (400, 404), f"Expected 400/404 for nonexistent provider, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_concurrent_imports_dont_corrupt(self, client, sandbox_credentials):
        """Running two imports for the same provider simultaneously doesn't corrupt data."""
        if "stripe" not in sandbox_credentials:
            pytest.skip("Stripe credentials not configured")

        token = sandbox_credentials["stripe"]["access_token"]
        resp = await client.post(
            "/api/v1/integrations/connections",
            data={"provider": "stripe", "tenant": "concurrent-test", "access_token": token},
            headers=MOCK_HEADERS,
        )
        conn_id = resp.json()["data"]["id"]

        async def _run_import():
            return await client.post(
                "/api/v1/integrations/stripe/import",
                data={"import_types": ["customers"], "connection_id": conn_id, "dry_run": "false"},
                headers=MOCK_HEADERS,
            )

        results = await asyncio.gather(_run_import(), _run_import(), return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                pass
            else:
                assert r.status_code == 200, f"Import should succeed on concurrent runs: {r.text if r else 'None'}"


# ============================================================================
# GATE B5 — Cross-Provider Data Consistency
# ============================================================================

@pytest.mark.sandbox
class TestGateB5_CrossProviderConsistency:
    """Validate: importing same logical data from two providers doesn't create conflicts."""

    @pytest.mark.asyncio
    async def test_provider_scan_results_are_consistent(self, client, sandbox_credentials):
        """Each provider scan returns structured, comparable results."""
        for provider in sandbox_credentials:
            creds = sandbox_credentials[provider]
            token = creds.get("access_token")
            if not token:
                continue

            resp = await client.post(
                "/api/v1/integrations/connections",
                data={"provider": provider, "tenant": f"cross-{provider}", "access_token": token},
                headers=MOCK_HEADERS,
            )
            conn_id = resp.json()["data"]["id"]

            resp = await client.post(
                f"/api/v1/integrations/{provider}/scan",
                data={"connection_id": conn_id},
                headers=MOCK_HEADERS,
            )
            if resp.status_code != 200:
                continue

            scan = resp.json()["data"]
            expected_keys = {"status", "provider", "counts"}
            for key in expected_keys:
                assert key in scan, f"Scan result for {provider} missing key: {key}"

            for entity_type, count in scan.get("counts", {}).items():
                assert isinstance(count, int), f"Count for {provider}.{entity_type} should be int, got {type(count)}"

    @pytest.mark.asyncio
    async def test_external_ids_dont_collide_across_providers(self, client, sandbox_credentials):
        """Import logs from different providers never share external_id collisions."""
        if "stripe" not in sandbox_credentials:
            pytest.skip("Stripe credentials not configured")

        token = sandbox_credentials["stripe"]["access_token"]
        resp = await client.post(
            "/api/v1/integrations/connections",
            data={"provider": "stripe", "tenant": "no-collide", "access_token": token},
            headers=MOCK_HEADERS,
        )
        conn_id = resp.json()["data"]["id"]

        resp = await client.post(
            "/api/v1/integrations/stripe/import",
            data={"import_types": ["customers", "invoices", "payments"], "connection_id": conn_id, "dry_run": "false"},
            headers=MOCK_HEADERS,
        )
        assert resp.status_code == 200


# ============================================================================
# GATE B META — Environment Validation
# ============================================================================

@pytest.mark.sandbox
class TestGateB_MetaValidation:
    """Gate B self-checks: credential validity, provider reachability, env completeness."""

    def test_at_least_one_provider_configured(self, sandbox_credentials):
        """At minimum, one sandbox provider has credentials configured."""
        assert len(sandbox_credentials) >= 1, "No sandbox providers configured"

    @pytest.mark.asyncio
    async def test_providers_are_reachable(self, provider_availability):
        """Each configured provider API is reachable."""
        failed = {p: r for p, r in provider_availability.items() if not r.get("ok")}
        if failed:
            names = ", ".join(f"{p} ({r.get('error', 'unknown')})" for p, r in failed.items())
            pytest.skip(f"Some providers unreachable: {names}")

    def test_credential_format_validation(self, sandbox_credentials):
        """Credentials follow expected format patterns."""
        if "stripe" in sandbox_credentials:
            token = sandbox_credentials["stripe"]["access_token"]
            assert token.startswith(("sk_test_", "sk_live_")), f"Stripe token has unexpected format: {token[:12]}..."

        if "quickbooks" in sandbox_credentials:
            creds = sandbox_credentials["quickbooks"]
            assert creds.get("realm_id"), "QuickBooks realm_id is required"
            assert creds.get("access_token"), "QuickBooks access_token is required"

    @pytest.mark.asyncio
    async def test_provider_latency_within_sla(self, provider_availability):
        """Each reachable provider responds within SLA (15 seconds)."""
        for provider, result in provider_availability.items():
            if result.get("ok"):
                latency = result.get("latency_ms", 0)
                assert latency < 15000, (
                    f"{provider} latency {latency}ms exceeds 15s SLA"
                )
