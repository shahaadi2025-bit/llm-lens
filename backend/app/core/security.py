"""Security headers and a small per-IP write limiter for public demo mode. Auth arrives in Phase 6."""
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        if request.url.path.startswith("/api"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window limiter for write requests, keyed by client IP. In-memory, so it is per-process:
    right for a single free-tier container, not for a multi-replica deployment (use Redis then)."""

    def __init__(self, app, limit_per_minute: int, path_prefix: str = "/api") -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._limit = limit_per_minute
        self._prefix = path_prefix
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        if request.method in WRITE_METHODS and request.url.path.startswith(self._prefix):
            now = time.monotonic()
            ip = request.client.host if request.client else "unknown"
            window = self._hits[ip]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self._limit:
                retry = max(1, int(60 - (now - window[0])))
                return JSONResponse({"detail": "Rate limit reached for the public demo. Please wait a minute."},
                                    status_code=429, headers={"Retry-After": str(retry)})
            window.append(now)
            if len(self._hits) > 5000:  # bound memory: drop idle clients
                for key in [k for k, v in self._hits.items() if not v or now - v[-1] > 60]:
                    del self._hits[key]
        return await call_next(request)
