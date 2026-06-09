import hashlib
import json
import logging
import re
from datetime import UTC
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.idempotency import IdempotencyKey

logger = logging.getLogger(__name__)


def compute_request_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


async def get_idempotent_response(
    db: AsyncSession,
    company_id: UUID,
    user_id: str,
    idempotency_key: str,
    request_hash: str,
) -> dict[str, Any] | None:
    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.company_id == company_id,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        return None

    if record.status == "processing":
        raise HTTPException(status_code=409, detail="Request is already being processed")

    if record.request_hash != request_hash:
        raise HTTPException(
            status_code=422,
            detail="Idempotency-Key reused with different request body",
        )

    if record.response_json:
        try:
            return json.loads(record.response_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return None


async def create_idempotency_record(
    db: AsyncSession,
    company_id: UUID,
    user_id: str,
    idempotency_key: str,
    request_hash: str,
) -> None:
    record = IdempotencyKey(
        company_id=company_id,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status="processing",
    )
    db.add(record)
    try:
        await db.flush()
    except Exception as e:
        # Do NOT rollback the outer session — the idempotency record INSERT
        # uses the same transaction. Rolling back would undo all prior work.
        existing = await get_idempotent_response(db, company_id, user_id, idempotency_key, request_hash)
        if existing is not None:
            raise HTTPException(status_code=409, detail="Duplicate idempotency key (concurrent request)") from e
        raise HTTPException(status_code=409, detail="Idempotency key conflict — retry with new key") from e


async def complete_idempotency_record(
    db: AsyncSession,
    company_id: UUID,
    user_id: str,
    idempotency_key: str,
    response_body: dict[str, Any],
    status: str = "completed",
) -> None:
    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.company_id == company_id,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
    )
    record = result.scalar_one_or_none()
    if record:
        record.status = status
        record.response_json = json.dumps(response_body, default=str)
        await db.flush()


def extract_idempotency_key(request: Request) -> str | None:
    key = request.headers.get("Idempotency-Key")
    if key:
        key = key.strip()
        if len(key) > 255:
            raise HTTPException(status_code=422, detail="Idempotency-Key too long (max 255 chars)")
        if not key:
            raise HTTPException(status_code=422, detail="Idempotency-Key cannot be empty")
        # HIGH-10 FIX: Validate key format — only allow printable ASCII alphanumeric, hyphens, underscores
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", key):
            raise HTTPException(
                status_code=422,
                detail="Idempotency-Key must contain only alphanumeric characters, hyphens, underscores, or dots",
            )
    return key


# LOW-3 FIX: Reduce idempotency retention from 48h to 10min (600s).
# Idempotency keys only need to cover the retry window + network delay,
# not multiple days. Shorter retention reduces DB bloat.
_IDEMPOTENCY_RETENTION_SECONDS = 600


async def cleanup_expired_idempotency_keys():
    from datetime import datetime, timedelta

    from sqlalchemy import delete

    from app.database import AsyncSessionLocal

    cutoff = datetime.now(UTC) - timedelta(seconds=_IDEMPOTENCY_RETENTION_SECONDS)
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at < cutoff))
            if result.rowcount > 0:
                await db.commit()
                logger.info("Cleaned up %d expired idempotency keys", result.rowcount)
    except Exception as e:
        logger.error("Failed to cleanup idempotency keys: %s", e)
