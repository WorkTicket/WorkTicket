import logging
import os
import time

logger = logging.getLogger(__name__)


class RedisPool:
    """Global Redis async connection pool singleton.

    Provides connection pooling for all Redis callers (rate limiter,
    concurrency, retry guard, WS tracking) to avoid creating a new
    TCP connection per operation.
    """

    def __init__(self):
        self._pool: object | None = None
        self._redis_url: str | None = None
        self._max_connections = 50
        self._last_health_check = 0.0
        self._health_interval = 15.0
        self._available = False

    async def _ensure_pool(self) -> bool:
        """Ensure the connection pool is initialized and healthy."""
        now = time.time()
        if self._available and (now - self._last_health_check) < self._health_interval:
            return True
        return await self._connect()

    async def _connect(self) -> bool:
        """Create or refresh the connection pool."""
        try:
            from app.config import get_settings

            settings = get_settings()
            url = settings.effective_redis_cache_url
            if not url or url == "__REQUIRED__":
                url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

            if self._pool is None or url != self._redis_url:
                if self._pool is not None:
                    try:
                        await self._pool.disconnect()  # type: ignore[attr-defined]
                    except Exception as e:
                        logger.debug("Redis pool disconnect failed: %s", e)
                from app.redis_sentinel import create_redis_from_url

                self._pool = create_redis_from_url(
                    url,
                    socket_connect_timeout=2.0,
                    socket_timeout=5.0,
                    socket_keepalive=True,
                    health_check_interval=15,
                    max_connections=self._max_connections,
                )
                self._redis_url = url

            await self._pool.ping()
            self._available = True
            self._last_health_check = time.time()
            return True
        except Exception as e:
            self._available = False
            logger.warning("Redis pool connection failed: %s", e)
            return False

    async def get_client(self):
        """Get a Redis client from the pool."""
        ok = await self._ensure_pool()
        if ok and self._pool:
            return self._pool
        return None

    async def close(self):
        """Close all connections in the pool."""
        if self._pool is not None:
            try:
                await self._pool.disconnect()  # type: ignore[attr-defined]
            except Exception as e:
                logger.debug("Redis pool disconnect failed: %s", e)
            self._pool = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def get_pool_stats(self) -> dict:
        """Return pool stats for metrics."""
        if self._pool is None:
            return {"available": False, "in_use": 0, "total": 0}
        try:
            info = self._pool.connection_pool if hasattr(self._pool, "connection_pool") else {}
            return {
                "available": self._available,
                "in_use": getattr(info, "_in_use_connections", 0) if hasattr(info, "_in_use_connections") else 0,
                "total": getattr(info, "_created_connections", 0) if hasattr(info, "_created_connections") else 0,
            }
        except Exception as e:
            logger.debug("Redis pool stats failed: %s", e)
            return {"available": self._available, "in_use": 0, "total": 0}


# Global singleton
redis_pool = RedisPool()


async def get_redis() -> object | None:
    """Convenience function to get Redis client from global pool."""
    return await redis_pool.get_client()  # type: ignore[no-any-return]
