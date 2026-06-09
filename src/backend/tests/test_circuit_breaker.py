import pytest

from app.ai.circuit_breaker import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_initial_state_is_closed():
    cb = CircuitBreaker(name="test", failure_threshold=3, cooldown_seconds=30.0)
    assert cb.state == CircuitState.CLOSED, "Circuit should start CLOSED"
    assert await cb.is_available() is True


@pytest.mark.asyncio
async def test_failure_threshold_triggers_open():
    cb = CircuitBreaker(name="test", failure_threshold=3, cooldown_seconds=30.0)
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.CLOSED, "Should still be CLOSED after 2 failures"
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN, "Should OPEN after 3 failures"
    assert await cb.is_available() is False


@pytest.mark.asyncio
async def test_success_resets_failure_count():
    cb = CircuitBreaker(name="test", failure_threshold=3, cooldown_seconds=30.0)
    await cb.record_failure()
    await cb.record_failure()
    await cb.record_success()
    await cb.record_failure()
    assert cb.state == CircuitState.CLOSED, "Success should reset failure count"
    assert cb.failure_count == 1, "Should have 1 failure after reset"


@pytest.mark.asyncio
async def test_half_open_after_cooldown():
    cb = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=0.1)
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN, "Should stay OPEN during cooldown"
    await cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN, "Should transition to HALF_OPEN after cooldown"


@pytest.mark.asyncio
async def test_half_open_failure_reopens():
    cb = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=0.01)
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN, "Should stay OPEN during cooldown"
    await cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN, "Failure in HALF_OPEN should re-OPEN"
