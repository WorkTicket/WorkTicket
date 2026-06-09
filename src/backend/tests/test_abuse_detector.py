from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.billing.abuse import AbuseDetector


@pytest.mark.asyncio
async def test_check_usage_spike_redis_down_returns_false():
    detector = AbuseDetector()
    with patch.object(detector, "_get_redis", return_value=None):
        result = await detector._check_usage_spike("company-1")
        assert result is False, "Should return False (no spike) when Redis is unavailable"


@pytest.mark.asyncio
async def test_check_usage_spike_redis_exception_returns_false():
    detector = AbuseDetector()
    mock_redis = AsyncMock()
    mock_redis.zcount.side_effect = Exception("Redis connection error")
    with patch.object(detector, "_get_redis", return_value=mock_redis):
        result = await detector._check_usage_spike("company-1")
        assert result is False, "Should return False (no spike) on Redis exception"


@pytest.mark.asyncio
async def test_check_usage_spike_below_threshold():
    detector = AbuseDetector()
    mock_redis = AsyncMock()
    mock_redis.zcount.return_value = 3
    with patch.object(detector, "_get_redis", return_value=mock_redis):
        result = await detector._check_usage_spike("company-1")
        assert result is False, "3 requests in window should not be a spike (threshold=10)"


@pytest.mark.asyncio
async def test_check_usage_spike_above_threshold():
    detector = AbuseDetector()
    mock_redis = AsyncMock()
    mock_redis.zcount.return_value = 15
    with patch.object(detector, "_get_redis", return_value=mock_redis):
        result = await detector._check_usage_spike("company-1")
        assert result is True, "15 requests in window should be a spike"


@pytest.mark.asyncio
async def test_risk_score_accumulation_triggers_quota_halving():
    db = AsyncMock()
    detector = AbuseDetector()
    account = MagicMock()
    account.risk_score = 40
    account.ai_disabled = False
    account.temp_quota_multiplier = None
    detector._get_account = AsyncMock(return_value=account)
    detector._check_usage_spike = AsyncMock(return_value=True)
    account.risk_score = 45
    detector._count_recent_failures = AsyncMock(return_value=0)

    score = await detector.check_and_update_risk(db, "company-1")

    assert score == 65, "Risk score should be 45 + 20 (spike) = 65"
    assert account.temp_quota_multiplier == 0.5, "Quota should be halved at risk > 50"


@pytest.mark.asyncio
async def test_risk_score_accumulation_triggers_ai_disable():
    db = AsyncMock()
    detector = AbuseDetector()
    account = MagicMock()
    account.risk_score = 55
    account.ai_disabled = False
    account.temp_quota_multiplier = None
    detector._get_account = AsyncMock(return_value=account)
    detector._check_usage_spike = AsyncMock(return_value=True)
    detector._count_recent_failures = AsyncMock(return_value=6)

    score = await detector.check_and_update_risk(db, "company-1")

    assert score > 70, "Risk score should exceed 70"
    assert account.ai_disabled is True, "AI should be disabled at risk > 70"
