"""Security headers and a small per-IP write limiter for public demo mode. Auth arrives in Phase 6."""
import logging
import re
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# The SPA uses self-hosted fonts and bundles only; React/Recharts need inline style attributes, nothing needs inline script.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; "
       "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
HSTS = "max-age=31536000; includeSubDomains"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, hsts: bool = False) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._hsts = hsts

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        path = request.url.path
        if path.startswith("/api"):
            response.headers.setdefault("Cache-Control", "no-store")
        elif path != "/api/docs":
            response.headers.setdefault("Content-Security-Policy", CSP)  # the API's Swagger page loads a CDN script, so it is exempt
        if self._hsts:
            response.headers.setdefault("Strict-Transport-Security", HSTS)
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


class BodyLimitMiddleware:
    """Reject request bodies over a limit, whether announced by Content-Length or streamed (chunked). Pure ASGI so the
    stream can be counted without buffering it."""

    def __init__(self, app, max_bytes: int = 1_000_000) -> None:  # type: ignore[no-untyped-def]
        self.app = app
        self.max = max_bytes

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max:
            return await self._reject(send)
        seen = 0
        rejected = False

        async def guarded_send(message):  # type: ignore[no-untyped-def]
            if not rejected:  # once our 413 is out, drop whatever the app tries to send after catching the failed read
                await send(message)

        async def limited():  # type: ignore[no-untyped-def]
            nonlocal seen, rejected
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max and not rejected:
                    rejected = True
                    await self._reject(send)  # answer 413 immediately, then abort the read
                    raise _TooLarge
            return message

        try:
            await self.app(scope, limited, guarded_send)
        except _TooLarge:
            pass

    @staticmethod
    async def _reject(send) -> None:  # type: ignore[no-untyped-def]
        body = b'{"detail":"request body too large"}'
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


class _TooLarge(Exception):
    pass


_SECRET_PATTERNS = [
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*)[^\s,;&\"']+"), r"\1[REDACTED]"),
    (re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^:/\s]+:)[^@\s]+(@)"), r"\1[REDACTED]\2"),
]


def redact(text: str) -> str:
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    """Scrub credentials from log lines before any handler sees them."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def install_log_redaction() -> None:
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "app"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactingFilter) for f in logger.filters):
            logger.addFilter(RedactingFilter())
