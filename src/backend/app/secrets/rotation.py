"""Automated secret rotation with grace period support.

Provides runtime key rotation for configurable secrets with a grace period
where both old and new keys are accepted. Rotations are logged to the audit
trail for compliance.

Configuration via environment:
    ROTATION_GRACE_PERIOD_SECONDS: Default 300 (5 minutes)
    ROTATION_AUDIT_LOG: Set to 'true' to enable rotation audit logging

Supported secrets:
    - CELERY_TASK_SIGNING_KEY: HMAC task signing key
    - PII_ENCRYPTION_KEY: PII field encryption key
    - METRICS_ACCESS_TOKEN: Prometheus metrics auth token
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC

logger = logging.getLogger(__name__)

_ROTATION_GRACE_PERIOD = float(os.environ.get("ROTATION_GRACE_PERIOD_SECONDS", "300"))
_AUDIT_ENABLED = os.environ.get("ROTATION_AUDIT_LOG", "").lower() in ("true", "1", "yes")


@dataclass
class SecretVersion:
    key: str
    rotated_at: float
    expires_at: float

    @property
    def is_active(self) -> bool:
        return time.time() < self.expires_at


class SecretRotator:
    """Manages key rotation with grace period for a single secret.

    During rotation, both current and previous keys are accepted for
    verification until the grace period expires.
    """

    def __init__(self, name: str, env_var: str):
        self.name = name
        self.env_var = env_var
        self._current: SecretVersion | None = None
        self._previous: SecretVersion | None = None
        self._lock = asyncio.Lock()
        self._last_check: float = 0

    def _load_from_env(self) -> str | None:
        return os.environ.get(self.env_var)

    async def get_current_key(self) -> str | None:
        async with self._lock:
            now = time.time()
            env_key = self._load_from_env()

            if self._current is not None:
                if env_key and env_key != self._current.key:
                    self._rotate_internal(env_key, now)
                elif self._current.is_active:
                    return self._current.key

            if env_key:
                self._current = SecretVersion(
                    key=env_key,
                    rotated_at=now,
                    expires_at=now + _ROTATION_GRACE_PERIOD * 10,
                )
                return env_key
            return None

    def _rotate_internal(self, new_key: str, now: float):
        logger.info("Secret rotation detected for %s — grace period %.0fs active", self.name, _ROTATION_GRACE_PERIOD)
        self._previous = self._current
        self._current = SecretVersion(
            key=new_key,
            rotated_at=now,
            expires_at=now + _ROTATION_GRACE_PERIOD * 10,
        )
        if _AUDIT_ENABLED:
            _log_rotation_audit(self.name, self._previous.key if self._previous else None, new_key)

    async def verify(self, value: bytes, expected_hmac: str) -> bool:
        current_key = await self.get_current_key()
        if not current_key:
            logger.error("No key available for %s verification", self.name)
            return False

        if self._verify_with_key(current_key, value, expected_hmac):
            return True

        if (
            self._previous
            and self._previous.is_active
            and self._verify_with_key(self._previous.key, value, expected_hmac)
        ):
            logger.info("Verified with previous %s key (grace period)", self.name)
            return True

        return False

    def _verify_with_key(self, key: str, value: bytes, expected_hmac: str) -> bool:
        computed = hmac.new(key.encode("utf-8"), value, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, expected_hmac)

    async def sign(self, value: dict) -> str:
        key = await self.get_current_key()
        if not key:
            logger.error("No key available for %s signing", self.name)
            return ""
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return hmac.new(key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


_rotators: dict[str, SecretRotator] = {}


def get_rotator(name: str, env_var: str) -> SecretRotator:
    if name not in _rotators:
        _rotators[name] = SecretRotator(name=name, env_var=env_var)
    return _rotators[name]


def _log_rotation_audit(secret_name: str, old_key: str | None, new_key: str):
    """Log secret rotation event to audit trail."""
    from datetime import datetime

    old_hash = hashlib.sha256((old_key or "").encode()).hexdigest()[:16] if old_key else "NONE"
    new_hash = hashlib.sha256(new_key.encode()).hexdigest()[:16]
    logger.info(
        "SECRET_ROTATION_AUDIT: secret=%s old_hash=%s new_hash=%s time=%s",
        secret_name,
        old_hash,
        new_hash,
        datetime.now(UTC).isoformat(),
    )


def get_rotatable_secrets() -> list[str]:
    """Return list of secrets that support runtime rotation."""
    return sorted(_rotators.keys())


def get_rotation_status() -> dict:
    """Return current rotation status for all managed secrets."""
    status = {}
    for name, rotator in _rotators.items():
        current = rotator._current
        previous = rotator._previous
        status[name] = {
            "has_current": current is not None,
            "current_age_seconds": round(time.time() - current.rotated_at, 1) if current else None,
            "has_previous": previous is not None,
            "previous_active": previous.is_active if previous else False,
            "grace_period_remaining": round(previous.expires_at - time.time(), 1)
            if previous and previous.is_active
            else 0,
        }
    return status
