import logging
import os
import uuid

from fastapi import Request

logger = logging.getLogger(__name__)

_OTEL_ENABLED = bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip())


async def tracing_middleware(request: Request, call_next):
    """FastAPI middleware that manages trace context propagation.

    1. Extracts W3C traceparent header or creates a new trace ID.
    2. Stores trace_id and span_id in request.state for downstream usage.
    3. Passes context to structured logging via a thread-local / contextvars carrier.
    4. Adds distributed tracing headers to the response.
    """
    _traceparent = request.headers.get("traceparent", "")
    _trace_id = None
    _span_id = None

    if _traceparent:
        parts = _traceparent.split("-")
        if len(parts) >= 2:
            _trace_id = parts[1]
        if len(parts) >= 3:
            _span_id = parts[2]
    if not _trace_id:
        _trace_id = uuid.uuid4().hex[:32]
    if not _span_id:
        _span_id = uuid.uuid4().hex[:16]

    _correlation_id = request.headers.get("X-Correlation-ID", request.headers.get("X-Request-ID", str(uuid.uuid4())))

    request.state.trace_id = _trace_id
    request.state.span_id = _span_id
    request.state.correlation_id = _correlation_id

    _set_logging_context(_trace_id, _span_id)

    response = await call_next(request)

    response.headers["X-Trace-ID"] = _trace_id
    response.headers["X-Span-ID"] = _span_id
    response.headers["X-Correlation-ID"] = _correlation_id

    _clear_logging_context()

    return response


try:
    from contextvars import ContextVar

    _trace_context: ContextVar[dict | None] = ContextVar("trace_context", default=None)

    def _set_logging_context(trace_id: str | None, span_id: str | None):
        _trace_context.set(
            {
                "trace_id": trace_id or "",
                "span_id": span_id or "",
            }
        )

    def _clear_logging_context():
        _trace_context.set({})

    def get_logging_context() -> dict:
        return _trace_context.get() or {}

except ImportError:
    import threading

    _local = threading.local()

    def _set_logging_context(trace_id: str | None, span_id: str | None):
        _local.trace_context = {
            "trace_id": trace_id or "",
            "span_id": span_id or "",
        }

    def _clear_logging_context():
        _local.trace_context = {}

    def get_logging_context() -> dict:
        return getattr(_local, "trace_context", {})
