import logging
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RequestBodySizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from app.config import get_settings

        settings = get_settings()
        max_size = settings.max_request_body_size

        content_length_str = request.headers.get("content-length")
        if content_length_str:
            try:
                content_length = int(content_length_str)
                if content_length > max_size:
                    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
                    logger.warning(
                        "Request body too large: method=%s path=%s size=%d max=%d",
                        request.method,
                        request.url.path,
                        content_length,
                        max_size,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "success": False,
                            "error": {
                                "code": "REQUEST_TOO_LARGE",
                                "message": f"Request body exceeds maximum size of {max_size} bytes",
                                "request_id": request_id,
                            },
                        },
                    )
            except (ValueError, TypeError):
                pass

        content_encoding = request.headers.get("transfer-encoding", "").lower()
        if "chunked" in content_encoding:
            body = b""
            async for chunk in request.stream():
                body += chunk
                if len(body) > max_size:
                    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
                    logger.warning(
                        "Chunked body too large: method=%s path=%s max=%d",
                        request.method,
                        request.url.path,
                        max_size,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "success": False,
                            "error": {
                                "code": "REQUEST_TOO_LARGE",
                                "message": f"Request body exceeds maximum size of {max_size} bytes",
                                "request_id": request_id,
                            },
                        },
                    )

            async def _replacement_body():
                yield body

            request._body = body
            request.stream = _replacement_body

        return await call_next(request)
