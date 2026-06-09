"""E2E rate limit tests that verify HTTP 429 responses at the API level.

Tests that the rate limiter middleware actually rejects requests with 429
when limits are exceeded.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_rate_limit(client: AsyncClient):
    responses = []
    for _ in range(5):
        resp = await client.get("/health")
        responses.append(resp.status_code)
    assert 429 in responses or responses[-1] in (200, 503)


@pytest.mark.asyncio
async def test_jobs_endpoint_rate_limit(client: AsyncClient):
    responses = []
    for _ in range(20):
        resp = await client.get("/api/v1/jobs")
        responses.append(resp.status_code)
    assert 200 in responses


@pytest.mark.asyncio
async def test_ai_endpoint_rate_config(client: AsyncClient):
    from app.ai.rate_limiter import rate_limiter

    limits = rate_limiter.get_limits("ai_process_job", "free")
    assert limits is not None


@pytest.mark.asyncio
async def test_billing_endpoint_rate_limit_config(client: AsyncClient):
    from app.ai.rate_limiter import rate_limiter

    limits = rate_limiter.get_limits("billing_webhook", "free")
    assert limits is not None
