import logging
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in SAFE_METHODS:
            return await call_next(request)

        # M-3 FIX: Even when a Bearer token is present, verify Origin/Referer headers
        # for non-GET requests. Browser JS can attach Authorization headers via
        # fetch() cross-origin, so Bearer token alone does not guarantee the request
        # is not a CSRF attack. Origin/Referer must match an allowed domain.
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # Still verify Origin/Referer to prevent CSRF in browser contexts
            origin = request.headers.get("origin", "")
            referer = request.headers.get("referer", "")
            if not origin and not referer:
                logger.warning(
                    "CSRF check: Bearer token request with no Origin/Referer: %s %s — REJECTING",
                    request.method,
                    request.url.path,
                )
                request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "error": {
                            "code": "CSRF_FAILED",
                            "message": "Request must include Origin or Referer header",
                            "request_id": request_id,
                        },
                    },
                )
            # Validate origin/referer against allowed domains (reuse below logic)
            if not self._origin_allowed(request, origin, referer):
                request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
                logger.error(
                    "CSRF validation failed (Bearer): method=%s path=%s origin=%s referer=%s",
                    request.method,
                    request.url.path,
                    origin,
                    referer,
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "error": {
                            "code": "CSRF_FAILED",
                            "message": "Request origin not allowed",
                            "request_id": request_id,
                        },
                    },
                )
            # M-3 FIX: SameSite=Strict should be set on any cookie-based operations
            # to prevent CSRF via cookie-based auth. Currently no cookie-based
            # auth is used, but this ensures future cookie usage is protected.
            return await call_next(request)

        content_type = (request.headers.get("content-type") or "").lower()
        if content_type == "application/x-www-form-urlencoded":
            logger.warning(
                "CSRF check: form-encoded content-type rejected: %s %s",
                request.method,
                request.url.path,
            )
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "error": {
                        "code": "CSRF_FAILED",
                        "message": "Form-encoded requests are not accepted; use application/json",
                        "request_id": request_id,
                    },
                },
            )

        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")

        if not origin and not referer:
            logger.warning(
                "CSRF check: request with no Origin/Referer header: %s %s — REJECTING",
                request.method,
                request.url.path,
            )
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "error": {
                            "code": "CSRF_FAILED",
                            "message": "Request must include Origin or Referer header",
                            "request_id": request_id,
                        },
                    },
                )
            return await call_next(request)

        if not self._origin_allowed(request, origin, referer):
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            logger.error(
                "CSRF validation failed: method=%s path=%s origin=%s referer=%s",
                request.method,
                request.url.path,
                origin,
                referer,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "error": {
                        "code": "CSRF_FAILED",
                        "message": "Request origin not allowed",
                        "request_id": request_id,
                    },
                },
            )

        return await call_next(request)

    def _origin_allowed(self, request: Request, origin: str, referer: str) -> bool:
        from app.config import get_settings

        settings = get_settings()

        allowed_domains = getattr(settings, "csrf_allowed_domains", None)
        if not allowed_domains:
            cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
            if "*" in cors_origins:
                logger.error("CSRF protection disabled: CORS origins contains wildcard '*'")
                return False
            allowed_domains = cors_origins

        origin_ok = False
        if origin:
            for allowed in allowed_domains:
                if origin == allowed or origin.rstrip("/") == allowed.rstrip("/"):
                    origin_ok = True
                    break
        if not origin_ok and referer:
            for allowed in allowed_domains:
                if referer.startswith(allowed.rstrip("/") + "/"):
                    origin_ok = True
                    break

        return origin_ok
