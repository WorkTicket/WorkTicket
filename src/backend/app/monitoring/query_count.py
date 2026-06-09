import logging
import os
from collections import defaultdict
from contextvars import ContextVar

logger = logging.getLogger(__name__)

_QUERY_COUNT_WARN_THRESHOLD = int(os.getenv("QUERY_COUNT_WARN_THRESHOLD", "20"))
_QUERY_COUNT_ERROR_THRESHOLD = int(os.getenv("QUERY_COUNT_ERROR_THRESHOLD", "50"))

_current_query_count: ContextVar[int] = ContextVar("current_query_count", default=0)
_current_request_path: ContextVar[str | None] = ContextVar("current_request_path", default=None)

_query_count_stats: dict[str, int] = defaultdict(int)
_query_count_by_endpoint: dict[str, list[int]] = defaultdict(list)
_MAX_ENDPOINT_SAMPLES = 100


class QueryCounter:
    """SQLAlchemy query count monitor to detect N+1 query patterns.

    Tracks the number of queries executed per request context
    and logs warnings when thresholds are exceeded. Maintains
    per-endpoint statistics for monitoring dashboards.
    """

    @staticmethod
    def reset():
        _current_query_count.set(0)

    @staticmethod
    def increment():
        count = _current_query_count.get()
        _current_query_count.set(count + 1)

    @staticmethod
    def get_count() -> int:
        return _current_query_count.get()

    @staticmethod
    def set_request_path(path: str):
        _current_request_path.set(path)

    @staticmethod
    def get_request_path() -> str | None:
        return _current_request_path.get()

    @staticmethod
    def record_endpoint(path: str, count: int):
        samples = _query_count_by_endpoint[path]
        samples.append(count)
        if len(samples) > _MAX_ENDPOINT_SAMPLES:
            _query_count_by_endpoint[path] = samples[-_MAX_ENDPOINT_SAMPLES:]
        if count > _QUERY_COUNT_WARN_THRESHOLD:
            _query_count_stats["warnings"] += 1
        if count > _QUERY_COUNT_ERROR_THRESHOLD:
            _query_count_stats["errors"] += 1
            logger.warning(
                "N+1 query pattern detected on %s: %d queries executed",
                path,
                count,
            )

    @staticmethod
    def check_and_warn():
        count = _current_query_count.get()
        path = _current_request_path.get() or "unknown"
        if count > _QUERY_COUNT_ERROR_THRESHOLD:
            logger.error(
                "HIGH QUERY COUNT on %s: %d queries (threshold: %d)",
                path,
                count,
                _QUERY_COUNT_ERROR_THRESHOLD,
            )
        elif count > _QUERY_COUNT_WARN_THRESHOLD:
            logger.warning(
                "ELEVATED QUERY COUNT on %s: %d queries (threshold: %d)",
                path,
                count,
                _QUERY_COUNT_WARN_THRESHOLD,
            )

    @staticmethod
    def get_stats() -> dict:
        top_endpoints = sorted(
            _query_count_by_endpoint.items(),
            key=lambda x: sum(x[1]) / max(len(x[1]), 1),
            reverse=True,
        )[:10]
        return {
            "total_warnings": _query_count_stats.get("warnings", 0),
            "total_errors": _query_count_stats.get("errors", 0),
            "warn_threshold": _QUERY_COUNT_WARN_THRESHOLD,
            "error_threshold": _QUERY_COUNT_ERROR_THRESHOLD,
            "top_endpoints": [
                {"path": path, "avg_queries": round(sum(counts) / max(len(counts), 1), 1), "samples": len(counts)}
                for path, counts in top_endpoints
            ],
        }


query_counter = QueryCounter()


def install_query_counter_listener():
    """Install SQLAlchemy event listener to count queries per request.

    Call this during app startup to enable N+1 detection.
    Queries are counted via the before_execute event and
    checked after each response.
    """
    try:
        from sqlalchemy import event

        from app.database import engine

        @event.listens_for(engine.sync_engine, "before_execute")
        def _before_execute(conn, clause, multiparams, params):
            QueryCounter.increment()

        logger.info(
            "Query counter listener installed (warn>%d, error>%d)",
            _QUERY_COUNT_WARN_THRESHOLD,
            _QUERY_COUNT_ERROR_THRESHOLD,
        )
        return True
    except Exception as e:
        logger.warning("Failed to install query counter listener: %s", e)
        return False
