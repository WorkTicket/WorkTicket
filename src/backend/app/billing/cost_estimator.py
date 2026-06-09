import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

ACU_TO_USD: float = 0.01


@dataclass
class JobCostBreakdown:
    text_cost: float
    vision_cost: float
    audio_cost: float
    total_cost: float
    total_acu: float


def estimate_job_cost(
    image_count: int = 0,
    has_audio: bool = False,
    text_tokens: int = 0,
) -> JobCostBreakdown:
    text_cost: float = 0.002
    if text_tokens > 2000:
        text_cost += 0.001 * ((text_tokens - 2000) / 1000)

    vision_cost: float = image_count * 0.01

    audio_cost: float = 0.008 if has_audio else 0.0

    total: float = (text_cost + vision_cost + audio_cost) * 1.2

    return JobCostBreakdown(
        text_cost=round(text_cost, 6),
        vision_cost=round(vision_cost, 6),
        audio_cost=round(audio_cost, 6),
        total_cost=round(total, 6),
        total_acu=round(total / ACU_TO_USD, 4),
    )


PLAN_TIERS: dict[str, dict[str, Any]] = {
    "free": {
        "quota_acu": 15.0,
        "max_cost_per_job": 0.01,
        "max_daily_cost_usd": 0.05,
        "routing": "local",
        "concurrency_limit": 1,
        "price_monthly": 0.0,
    },
    "starter": {
        "quota_acu": 200.0,
        "max_cost_per_job": 0.03,
        "max_daily_cost_usd": 0.50,
        "routing": "hybrid",
        "concurrency_limit": 2,
        "price_monthly": 19.0,
    },
    "pro": {
        "quota_acu": 600.0,
        "max_cost_per_job": 0.05,
        "max_daily_cost_usd": 2.00,
        "routing": "cloud",
        "concurrency_limit": 5,
        "price_monthly": 49.0,
    },
    "business": {
        "quota_acu": 2500.0,
        "max_cost_per_job": 0.10,
        "max_daily_cost_usd": 10.00,
        "routing": "cloud",
        "concurrency_limit": 10,
        "price_monthly": 149.0,
    },
    "enterprise": {
        "quota_acu": 10000.0,
        "max_cost_per_job": 0.50,
        "max_daily_cost_usd": 50.00,
        "routing": "cloud",
        "concurrency_limit": 20,
        "price_monthly": 500.0,
    },
}
