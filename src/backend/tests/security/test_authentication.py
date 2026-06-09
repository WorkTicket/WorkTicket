import pytest


@pytest.mark.asyncio
async def test_deactivated_user_token_rejected(client):
    from sqlalchemy import select

    from app.auth.dependencies import get_current_user
    from app.database import get_db
    from app.jobs.models import User

    async for db in get_db():
        result = await db.execute(select(User).where(User.id == "test-user-id"))
        user = result.scalar_one_or_none()
        assert user is not None

        user.is_active = False
        user.token_version += 1
        await db.flush()

    deactivated = User(
        id="test-user-id",
        company_id=user.company_id,
        email="test@example.com",
        name="Test User",
        role="owner",
        is_active=False,
        token_version=user.token_version - 1,
    )
    client.app.dependency_overrides[get_current_user] = lambda: deactivated
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401

    async for db in get_db():
        result = await db.execute(select(User).where(User.id == "test-user-id"))
        user = result.scalar_one_or_none()
        user.is_active = True
        user.token_version = 0
        await db.flush()


@pytest.mark.asyncio
async def test_unauthenticated_access_blocked(client):
    client.app.dependency_overrides.clear()

    protected = [
        "/api/v1/auth/me",
        "/api/v1/jobs",
        "/api/v1/ai/metrics",
    ]
    for path in protected:
        resp = await client.get(path)
        assert resp.status_code in (401, 403), f"{path} returned {resp.status_code}"
