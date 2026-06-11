from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20

    model_config = ConfigDict(json_schema_extra={"example": {"page": 1, "page_size": 20}})


class CursorPaginationParams(BaseModel):
    """SC1: Cursor-based pagination for performant analytics queries.

    Uses an opaque cursor (base64-encoded timestamp+id) instead of offset/limit.
    Cursor-based pagination avoids the performance cliff of large offsets
    on time-series data and is resilient to insertions during pagination.

    Falls back to page-based pagination if cursor is not provided.
    """

    cursor: str | None = None
    page_size: int = 50
    direction: str = "next"  # next | prev

    model_config = ConfigDict(json_schema_extra={"example": {"cursor": None, "page_size": 50, "direction": "next"}})


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(
        json_schema_extra={"example": {"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0}}
    )


class CursorPaginatedResponse[T](BaseModel):
    """SC1: Cursor-based paginated response for analytics.

    Includes next_cursor and prev_cursor for bidirectional traversal.
    """

    items: list[T]
    next_cursor: str | None = None
    prev_cursor: str | None = None
    page_size: int
    has_more: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"items": [], "next_cursor": None, "prev_cursor": None, "page_size": 50, "has_more": False}
        }
    )


def encode_cursor(timestamp: datetime, item_id: str | int) -> str:
    """Encode a cursor from a timestamp and item ID.

    Uses base64-encoded ISO timestamp + ID for sortable, opaque cursors.
    """
    import base64

    ts_str = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
    raw = f"{ts_str}|{item_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    """Decode a cursor into (timestamp, item_id)."""
    import base64

    try:
        cursor = cursor + "=" * (4 - len(cursor) % 4)  # Re-pad
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        parts = raw.rsplit("|", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid cursor format: {raw}")
        ts = datetime.fromisoformat(parts[0]) if parts[0] else None
        return ts, parts[1]  # type: ignore[return-value]
    except Exception as e:
        raise ValueError(f"Invalid cursor: {e}") from e
