"""Tenant-aware Redis key namespacing for per-tenant isolation.

Wraps Redis client operations with automatic tenant key prefixing
to prevent cross-tenant cache leakage and ensure key isolation.

Usage:
    from app.db.redis_tenant import tenant_redis

    # All keys are automatically prefixed with tenant ID:
    await tenant_redis.set("my_key", "value", tenant_id="abc-123")
    # Actual Redis key: "tnt:abc-123:my_key"

    # For cache Redis (LRU eviction), keys are prefixed for isolation.
    # For broker Redis (noeviction), tenant isolation is by design.
"""

import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

_TENANT_KEY_PREFIX = "tnt"
_SEPARATOR = ":"


def _tenant_key(tenant_id: str, key: str) -> str:
    """Build a tenant-prefixed Redis key."""
    return f"{_TENANT_KEY_PREFIX}{_SEPARATOR}{tenant_id}{_SEPARATOR}{key}"


def _tenant_key_pattern(tenant_id: str, pattern: str = "*") -> str:
    """Build a tenant-scoped Redis key pattern for scanning."""
    return f"{_TENANT_KEY_PREFIX}{_SEPARATOR}{tenant_id}{_SEPARATOR}{pattern}"


class TenantRedis:
    """Tenant-aware Redis wrapper with automatic key prefixing."""

    def __init__(self):
        self._redis = None

    def _get_client(self):
        if self._redis is None:
            from app.sync_redis_pool import get_sync_redis

            self._redis = get_sync_redis()
        return self._redis

    def set(self, key: str, value: Any, tenant_id: str, ex: int | None = None) -> bool:
        """Set a tenant-scoped key."""
        r = self._get_client()
        if r is None:
            return False
        try:
            r.set(_tenant_key(tenant_id, key), value, ex=ex)
            return True
        except Exception as e:
            logger.debug("TenantRedis.set failed for %s: %s", key, e)
            return False

    def get(self, key: str, tenant_id: str) -> Any | None:
        """Get a tenant-scoped key."""
        r = self._get_client()
        if r is None:
            return None
        try:
            return r.get(_tenant_key(tenant_id, key))
        except Exception as e:
            logger.debug("TenantRedis.get failed for %s: %s", key, e)
            return None

    def delete(self, key: str, tenant_id: str) -> bool:
        """Delete a tenant-scoped key."""
        r = self._get_client()
        if r is None:
            return False
        try:
            r.delete(_tenant_key(tenant_id, key))
            return True
        except Exception as e:
            logger.debug("TenantRedis.delete failed for %s: %s", key, e)
            return False

    def exists(self, key: str, tenant_id: str) -> bool:
        """Check if a tenant-scoped key exists."""
        r = self._get_client()
        if r is None:
            return False
        try:
            return bool(r.exists(_tenant_key(tenant_id, key)))
        except Exception as e:
            logger.debug("TenantRedis.exists failed for %s: %s", key, e)
            return False

    def expire(self, key: str, tenant_id: str, seconds: int) -> bool:
        """Set TTL on a tenant-scoped key."""
        r = self._get_client()
        if r is None:
            return False
        try:
            r.expire(_tenant_key(tenant_id, key), seconds)
            return True
        except Exception as e:
            logger.debug("TenantRedis.expire failed for %s: %s", key, e)
            return False

    def ttl(self, key: str, tenant_id: str) -> int | None:
        """Get TTL of a tenant-scoped key."""
        r = self._get_client()
        if r is None:
            return None
        try:
            return r.ttl(_tenant_key(tenant_id, key))
        except Exception as e:
            logger.debug("TenantRedis.ttl failed for %s: %s", key, e)
            return None

    def incr(self, key: str, tenant_id: str, amount: int = 1) -> int | None:
        """Increment a tenant-scoped counter."""
        r = self._get_client()
        if r is None:
            return None
        try:
            return r.incr(_tenant_key(tenant_id, key), amount)
        except Exception as e:
            logger.debug("TenantRedis.incr failed for %s: %s", key, e)
            return None

    def decr(self, key: str, tenant_id: str, amount: int = 1) -> int | None:
        """Decrement a tenant-scoped counter."""
        return self.incr(key, tenant_id, -amount)

    def scan(self, cursor: int, tenant_id: str, pattern: str = "*", count: int = 100):
        """Scan tenant-scoped keys."""
        r = self._get_client()
        if r is None:
            return 0, []
        try:
            return r.scan(cursor, match=_tenant_key_pattern(tenant_id, pattern), count=count)
        except Exception as e:
            logger.debug("TenantRedis.scan failed for %s: %s", pattern, e)
            return 0, []

    def get_tenant_memory_estimate(self, tenant_id: str) -> int | None:
        """Estimate memory used by a tenant's keys using Redis DEBUG.

        Returns approximate bytes or None if unavailable.
        """
        total = 0
        cursor = 0
        r = self._get_client()
        if r is None:
            return None
        try:
            while True:
                cursor, keys = r.scan(cursor, match=_tenant_key_pattern(tenant_id), count=200)
                for key in keys:
                    with contextlib.suppress(Exception):
                        total += r.memory_usage(key) or 0
                if cursor == 0:
                    break
            return total
        except Exception as e:
            logger.debug("TenantRedis.get_tenant_memory failed: %s", e)
            return None

    def delete_all_tenant_keys(self, tenant_id: str) -> int:
        """Delete all keys belonging to a tenant.

        Used during tenant deletion to clean up Redis state.
        """
        count = 0
        cursor = 0
        r = self._get_client()
        if r is None:
            return 0
        try:
            while True:
                cursor, keys = r.scan(cursor, match=_tenant_key_pattern(tenant_id), count=500)
                if keys:
                    r.delete(*keys)
                    count += len(keys)
                if cursor == 0:
                    break
            logger.info("Deleted %d Redis keys for tenant %s", count, tenant_id)
            return count
        except Exception as e:
            logger.error("Failed to delete tenant keys for %s: %s", tenant_id, e)
            return count


tenant_redis = TenantRedis()
