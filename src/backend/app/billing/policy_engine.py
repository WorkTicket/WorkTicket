import logging
from dataclasses import dataclass
from enum import StrEnum

from app.billing.cost_estimator import PLAN_TIERS

logger = logging.getLogger(__name__)


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    REJECT = "REJECT"
    DEGRADE_TO_LOCAL = "DEGRADE_TO_LOCAL"
    SKIP_VISION = "SKIP_VISION"
    SKIP_AUDIO = "SKIP_AUDIO"
    REDUCE_MODEL = "REDUCE_MODEL"


@dataclass
class PolicyResult:
    decision: PolicyDecision
    reason: str
    routing_override: str = ""


async def evaluate_policy(
    plan: str,
    estimated_cost_usd: float,
    has_vision: bool = False,
    has_audio: bool = False,
    system_load: int = 0,
) -> PolicyResult:
    tier = PLAN_TIERS.get(plan, PLAN_TIERS["free"])
    max_cost = tier["max_cost_per_job"]
    routing = tier["routing"]

    if estimated_cost_usd > max_cost * 2:
        return PolicyResult(
            decision=PolicyDecision.REJECT,
            reason=f"cost ${estimated_cost_usd:.4f} exceeds 2x tier max ${max_cost:.2f}",
        )

    if estimated_cost_usd > max_cost:
        if has_vision and estimated_cost_usd > max_cost * 1.5:
            return PolicyResult(
                decision=PolicyDecision.SKIP_VISION,
                reason=f"cost ${estimated_cost_usd:.4f} exceeds ${max_cost:.2f}, skipping vision",
                routing_override="local",
            )
        if has_audio:
            return PolicyResult(
                decision=PolicyDecision.SKIP_AUDIO,
                reason=f"cost ${estimated_cost_usd:.4f} exceeds ${max_cost:.2f}, skipping audio",
                routing_override="local",
            )
        return PolicyResult(
            decision=PolicyDecision.REDUCE_MODEL,
            reason=f"cost ${estimated_cost_usd:.4f} exceeds ${max_cost:.2f}, reducing model quality",
            routing_override="local",
        )

    if plan == "free":
        return PolicyResult(
            decision=PolicyDecision.DEGRADE_TO_LOCAL,
            reason="free tier: local only",
            routing_override="local",
        )

    if system_load > 20:
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason=f"high system load ({system_load}), routing to cloud",
            routing_override="cloud",
        )

    return PolicyResult(
        decision=PolicyDecision.ALLOW,
        reason=f"within tier limits, default routing: {routing}",
        routing_override=routing,
    )
