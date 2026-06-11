"""Redis-backed cache for Stripe subscription data.

Provides offline-mode caching so the application can continue serving
subscription-dependent features when the Stripe API is unreachable.

Architecture:
  - Subscription data is cached in Redis with a configurable TTL (default 300s).
  - On successful Stripe API calls, the cache is populated/refreshed.
  - On Stripe API failure (circuit breaker open or timeout), the cache is
    consulted as fallback.
  - Webhook receipt invalidates or updates the cache immediately.

Cache key scheme:
    stripe:sub:{stripe_subscription_id} -> JSON with fields:
        plan, customer_id, status, cached_at, expires_at

    stripe:customer:{stripe_customer_id} -> subscription_id (lookup helper)

Usage:
    from app.billing.stripe_cache import (
        get_cached_subscription,
        set_cached_subscription,
        invalidate_subscription_cache,
        resolve_plan_from_price_id,
    )

    # On successful Stripe retrieve:
    await set_cached_subscription(sub_id, {"plan": "pro", "status": "active", ...})

    # On Stripe failure:
    cached = await get_cached_subscription(sub_id)
    if cached:
        # use cached data
        pass

    # On webhook receipt:
    await invalidate_subscription_cache(sub_id)
"""

import contextlib
import json
import logging
import time

logger = logging.getLogger(__name__)

_STRIPE_PRICE_MAP_CACHE = None
_STRIPE_PRICE_MAP_LOADED = 0.0
_STRIPE_PRICE_MAP_TTL = 60.0


def resolve_plan_from_price_id(price_id: str) -> str:
    global _STRIPE_PRICE_MAP_CACHE, _STRIPE_PRICE_MAP_LOADED
    import json as _json

    now = __import__("time").time()
    if not _STRIPE_PRICE_MAP_CACHE or (now - _STRIPE_PRICE_MAP_LOADED) > _STRIPE_PRICE_MAP_TTL:
        try:
            from app.config import get_settings

            s = get_settings()
            _STRIPE_PRICE_MAP_CACHE = _json.loads(s.stripe_price_map) if s.stripe_price_map else {}
            _STRIPE_PRICE_MAP_LOADED = now
        except Exception:
            _STRIPE_PRICE_MAP_CACHE = _STRIPE_PRICE_MAP_CACHE or {}
    if _STRIPE_PRICE_MAP_CACHE:
        for pname, pid in _STRIPE_PRICE_MAP_CACHE.items():
            if pid == price_id:
                return pname  # type: ignore[no-any-return]
    return "unknown"


_CACHE_PREFIX = "stripe:sub:"
_CUSTOMER_PREFIX = "stripe:customer:"
_DEFAULT_TTL = 300  # 5 minutes, overridable via STRIPE_CACHE_TTL env


def _get_ttl() -> int:
    try:
        from app.config import get_settings

        return get_settings().stripe_cache_ttl
    except Exception:
        return int(_DEFAULT_TTL)


async def _get_redis():
    """Get Redis client from the shared pool."""
    try:
        from app.redis import get_redis

        return await get_redis()
    except Exception as e:
        logger.warning("Stripe cache: Redis unavailable: %s", e)
        return None


async def get_cached_subscription(
    stripe_subscription_id: str,
) -> dict | None:
    """Retrieve a cached subscription record.

    Returns None if the cache key does not exist, has expired, or Redis
    is unavailable.
    """
    if not stripe_subscription_id:
        return None
    r = await _get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(f"{_CACHE_PREFIX}{stripe_subscription_id}")
        if raw is None:
            return None
        data = json.loads(raw)
        # Check expiry inline (Redis TTL is the primary mechanism, but this
        # guards against stale data if TTL was set very long by accident).
        if data.get("expires_at", 0) < time.time():
            await r.delete(f"{_CACHE_PREFIX}{stripe_subscription_id}")
            return None
        return data  # type: ignore[no-any-return]
    except Exception as e:
        logger.warning("Stripe cache read error for %s: %s", stripe_subscription_id, e)
        return None


async def set_cached_subscription(
    stripe_subscription_id: str,
    data: dict,
    ttl: int | None = None,
) -> bool:
    """Store a subscription record in the cache.

    ``data`` should include at minimum: ``plan``, ``status`` (e.g. active,
    past_due, canceled), and optionally ``customer_id``.

    Returns True on success, False on failure.
    """
    if not stripe_subscription_id:
        return False
    r = await _get_redis()
    if r is None:
        return False
    try:
        ttl = ttl or _get_ttl()
        now = time.time()
        payload = {
            **data,
            "cached_at": now,
            "expires_at": now + ttl,
        }
        key = f"{_CACHE_PREFIX}{stripe_subscription_id}"
        await r.set(key, json.dumps(payload), ex=ttl)

        # Maintain customer_id -> subscription_id index for lookups
        customer_id = data.get("customer_id") or data.get("customer")
        if customer_id:
            await r.set(
                f"{_CUSTOMER_PREFIX}{customer_id}",
                stripe_subscription_id,
                ex=ttl,
            )

        logger.debug(
            "Cached subscription %s (plan=%s, status=%s, ttl=%ds)",
            stripe_subscription_id,
            data.get("plan"),
            data.get("status"),
            ttl,
        )
        return True
    except Exception as e:
        logger.warning("Stripe cache write error for %s: %s", stripe_subscription_id, e)
        return False


async def invalidate_subscription_cache(
    stripe_subscription_id: str | None = None,
    stripe_customer_id: str | None = None,
) -> bool:
    """Remove cached subscription data.

    Pass either the subscription ID or the customer ID (or both).
    Returns True if at least one key was deleted.
    """
    r = await _get_redis()
    if r is None:
        return False
    keys_to_delete = []
    if stripe_subscription_id:
        keys_to_delete.append(f"{_CACHE_PREFIX}{stripe_subscription_id}")
    if stripe_customer_id:
        # Look up subscription_id from customer index, then delete both
        try:
            sub_id = await r.get(f"{_CUSTOMER_PREFIX}{stripe_customer_id}")
            if sub_id:
                sub_id = sub_id.decode() if isinstance(sub_id, bytes) else sub_id
                keys_to_delete.append(f"{_CACHE_PREFIX}{sub_id}")
            keys_to_delete.append(f"{_CUSTOMER_PREFIX}{stripe_customer_id}")
        except Exception:
            keys_to_delete.append(f"{_CUSTOMER_PREFIX}{stripe_customer_id}")
    if not keys_to_delete:
        return False
    try:
        await r.delete(*keys_to_delete)
        logger.debug("Invalidated stripe cache keys: %s", keys_to_delete)
        return True
    except Exception as e:
        logger.warning("Stripe cache invalidation error: %s", e)
        return False


async def get_cached_subscription_by_customer(
    stripe_customer_id: str,
) -> dict | None:
    """Look up a cached subscription by customer ID."""
    if not stripe_customer_id:
        return None
    r = await _get_redis()
    if r is None:
        return None
    try:
        sub_id = await r.get(f"{_CUSTOMER_PREFIX}{stripe_customer_id}")
        if sub_id is None:
            return None
        sub_id = sub_id.decode() if isinstance(sub_id, bytes) else sub_id
        return await get_cached_subscription(sub_id)
    except Exception as e:
        logger.warning(
            "Stripe cache customer lookup error for %s: %s",
            stripe_customer_id,
            e,
        )
        return None


async def set_cache_from_stripe_object(stripe_subscription: object) -> bool:
    """Convenience: extract fields from a Stripe Subscription object and cache.

    Accepts either a Stripe library object (has .id, .items, etc.) or a raw dict.
    """
    if hasattr(stripe_subscription, "id"):
        sub_id = stripe_subscription.id
        status = getattr(stripe_subscription, "status", "unknown")
        customer_id = getattr(stripe_subscription, "customer", None)
        plan = "unknown"
        if hasattr(stripe_subscription, "items") and stripe_subscription.items:
            for item in stripe_subscription.items.data or []:
                price_id = getattr(getattr(item, "price", None), "id", None)
                if price_id:
                    with contextlib.suppress(Exception):
                        plan = resolve_plan_from_price_id(price_id)
        data = {
            "plan": plan,
            "status": status,
            "customer_id": customer_id,
        }
        return await set_cached_subscription(sub_id, data)
    elif isinstance(stripe_subscription, dict):
        sub_id = stripe_subscription.get("id")
        if not sub_id:
            return False
        plan = "unknown"
        for item in (stripe_subscription.get("items") or {}).get("data", []):
            price_id = (item.get("price") or {}).get("id", "")
            if price_id:
                with contextlib.suppress(Exception):
                    plan = resolve_plan_from_price_id(price_id)
        data = {
            "plan": plan,
            "status": stripe_subscription.get("status", "unknown"),
            "customer_id": stripe_subscription.get("customer"),
        }
        return await set_cached_subscription(sub_id, data)
    return False
