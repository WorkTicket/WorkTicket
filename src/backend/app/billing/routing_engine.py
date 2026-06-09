import logging
from dataclasses import dataclass

from app.billing.cost_estimator import PLAN_TIERS

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    target: str
    model_quality: str
    skip_vision: bool
    skip_audio: bool
    reason: str


async def get_system_load() -> int:
    try:
        from app.ai.rate_limiter import _get_redis

        redis = await _get_redis()
        if redis:
            total = 0
            for qname in ("default", "ai_text", "ai_audio", "ai_image"):
                length = await redis.llen(qname)
                total += length
            return total
        return 0
    except Exception:
        logger.warning("Redis unavailable for system load — assuming high load")
        return 999


async def route_ai_job(
    plan: str,
    estimated_cost_usd: float,
    has_vision: bool = False,
    has_audio: bool = False,
) -> RoutingDecision:
    tier = PLAN_TIERS.get(plan, PLAN_TIERS["free"])
    routing_pref = tier["routing"]

    system_load = await get_system_load()
    system_loaded = system_load > 10

    if plan == "free":
        return RoutingDecision(
            target="local",
            model_quality="low",
            skip_vision=has_vision,
            skip_audio=False,
            reason="free_tier: local only",
        )

    if plan == "starter":
        if system_loaded and estimated_cost_usd > 0.01:
            return RoutingDecision(
                target="cloud",
                model_quality="medium",
                skip_vision=False,
                skip_audio=False,
                reason="starter: cloud due to system load + cost",
            )
        if estimated_cost_usd < 0.005:
            return RoutingDecision(
                target="local",
                model_quality="low",
                skip_vision=False,
                skip_audio=False,
                reason="starter: local for low-cost job",
            )
        return RoutingDecision(
            target="cloud" if estimated_cost_usd > 0.01 else "local",
            model_quality="medium",
            skip_vision=False,
            skip_audio=False,
            reason=f"starter: hybrid routing (cost={estimated_cost_usd})",
        )

    if plan in ("pro", "business", "enterprise"):
        if system_loaded:
            return RoutingDecision(
                target="cloud",
                model_quality="high",
                skip_vision=False,
                skip_audio=False,
                reason=f"{plan}: cloud priority",
            )
        if routing_pref == "cloud":
            return RoutingDecision(
                target="cloud",
                model_quality="high",
                skip_vision=False,
                skip_audio=False,
                reason=f"{plan}: cloud default",
            )
        return RoutingDecision(
            target="cloud",
            model_quality="high",
            skip_vision=False,
            skip_audio=False,
            reason=f"{plan}: cloud-first routing",
        )

    return RoutingDecision(
        target="local",
        model_quality="low",
        skip_vision=False,
        skip_audio=False,
        reason="default: local",
    )


async def should_downgrade_job(
    plan: str,
    estimated_cost_usd: float,
    has_vision: bool,
    has_audio: bool,
) -> RoutingDecision:
    tier = PLAN_TIERS.get(plan, PLAN_TIERS["free"])
    max_cost = tier["max_cost_per_job"]

    if estimated_cost_usd > max_cost:
        if has_vision and estimated_cost_usd > max_cost:
            return RoutingDecision(
                target="local",
                model_quality="low",
                skip_vision=True,
                skip_audio=False,
                reason=f"cost {estimated_cost_usd} exceeds tier max {max_cost}, skipping vision",
            )
        if has_audio:
            return RoutingDecision(
                target="local",
                model_quality="low",
                skip_vision=has_vision,
                skip_audio=True,
                reason="cost exceeds limit, skipping audio",
            )

    return RoutingDecision(
        target="local" if plan == "free" else "cloud",
        model_quality="low" if plan == "free" else "medium",
        skip_vision=False,
        skip_audio=False,
        reason="within tier limits",
    )
