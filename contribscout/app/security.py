"""Small ASGI boundary for protecting the remote MCP transport."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from collections import OrderedDict
from typing import Any


def validate_remote_auth(host: str, token: str | None) -> None:
    """Fail closed when HTTP is bound to a non-loopback interface."""
    is_loopback = host.lower() in {"127.0.0.1", "localhost", "::1"}
    if not is_loopback and len((token or "").strip()) < 32:
        raise RuntimeError(
            "Remote Streamable HTTP requires MCP_AUTH_TOKEN with at least 32 characters. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )


class SlidingWindowLimiter:
    """Per-credential sliding-window limiter with bounded memory."""

    def __init__(self, limit: int = 30, window_seconds: int = 60, max_buckets: int = 1024):
        if limit < 1 or window_seconds < 1 or max_buckets < 1:
            raise ValueError("Rate-limit settings must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_buckets = max_buckets
        self._buckets: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def consume(self, key: str, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        async with self._lock:
            timestamps = [stamp for stamp in self._buckets.get(key, []) if stamp > cutoff]
            if len(timestamps) >= self.limit:
                self._buckets[key] = timestamps
                self._buckets.move_to_end(key)
                return False, max(1, int(timestamps[0] + self.window_seconds - current + 0.999))
            timestamps.append(current)
            self._buckets[key] = timestamps
            self._buckets.move_to_end(key)
            while len(self._buckets) > self.max_buckets:
                self._buckets.popitem(last=False)
            return True, 0


class McpAccessMiddleware:
    """Require a bearer secret and throttle calls to the remote MCP endpoint."""

    def __init__(self, app: Any, token: str | None, requests_per_minute: int = 30):
        self.app = app
        self.token = token.strip() if token and token.strip() else None
        self.limiter = SlidingWindowLimiter(limit=requests_per_minute)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        if path == "/healthz" and method in {"GET", "HEAD"}:
            await self._respond(send, 200, {"status": "ok"}, head=method == "HEAD")
            return
        if path != "/mcp":
            await self._respond(send, 404, {"error": "not_found", "message": "Endpoint not found"})
            return
        if self.token is None:
            await self._respond(
                send,
                503,
                {"error": "auth_not_configured", "message": "Remote MCP authentication is not configured"},
            )
            return

        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"")
        scheme, _, supplied = authorization.partition(b" ")
        try:
            supplied_token = supplied.decode("utf-8")
        except UnicodeDecodeError:
            supplied_token = ""
        if scheme.lower() != b"bearer" or not hmac.compare_digest(supplied_token, self.token):
            await self._respond(
                send,
                401,
                {"error": "unauthorized", "message": "Provide the configured bearer token"},
                extra_headers=[(b"www-authenticate", b'Bearer realm="ContribScout MCP"')],
            )
            return

        # Hash the credential so secrets never become keys in limiter state or logs.
        bucket = hashlib.sha256(self.token.encode("utf-8")).hexdigest()
        allowed, retry_after = await self.limiter.consume(bucket)
        if not allowed:
            await self._respond(
                send,
                429,
                {"error": "rate_limited", "message": "Request limit exceeded; retry shortly"},
                extra_headers=[(b"retry-after", str(retry_after).encode("ascii"))],
            )
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _respond(
        send: Any,
        status: int,
        payload: dict[str, str],
        *,
        head: bool = False,
        extra_headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
            (b"x-content-type-options", b"nosniff"),
        ]
        headers.extend(extra_headers or [])
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": b"" if head else body})
