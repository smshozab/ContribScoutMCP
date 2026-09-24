import httpx
import pytest

from contribscout.app.security import McpAccessMiddleware, SlidingWindowLimiter, validate_remote_auth


async def _ok_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"mcp"})


@pytest.mark.asyncio
async def test_health_endpoint_does_not_require_authentication():
    app = McpAccessMiddleware(_ok_app, token="secret-token-with-more-than-32-characters")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_mcp_endpoint_rejects_missing_and_invalid_bearer_token():
    app = McpAccessMiddleware(_ok_app, token="secret-token-with-more-than-32-characters")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.post("/mcp")
        invalid = await client.post("/mcp", headers={"Authorization": "Bearer wrong"})
    assert missing.status_code == invalid.status_code == 401
    assert missing.headers["www-authenticate"].startswith("Bearer")


@pytest.mark.asyncio
async def test_mcp_endpoint_throttles_calls_after_limit():
    app = McpAccessMiddleware(_ok_app, token="secret-token-with-more-than-32-characters", requests_per_minute=1)
    headers = {"Authorization": "Bearer secret-token-with-more-than-32-characters"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/mcp", headers=headers)
        second = await client.post("/mcp", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1


@pytest.mark.asyncio
async def test_missing_server_token_fails_closed_for_mcp_endpoint():
    app = McpAccessMiddleware(_ok_app, token=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/mcp")
    assert response.status_code == 503
    assert response.json()["error"] == "auth_not_configured"


@pytest.mark.asyncio
async def test_unknown_paths_are_not_forwarded_to_mcp_server():
    app = McpAccessMiddleware(_ok_app, token="secret-token-with-more-than-32-characters")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sliding_window_limiter_returns_retry_time_and_expires_old_entries():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=10)
    allowed, _ = await limiter.consume("client", now=5)
    blocked, retry_after = await limiter.consume("client", now=7)
    allowed_again, _ = await limiter.consume("client", now=16)
    assert allowed is True
    assert blocked is False and retry_after == 8
    assert allowed_again is True


def test_remote_listener_requires_long_secret_but_localhost_does_not():
    validate_remote_auth("127.0.0.1", None)
    validate_remote_auth("localhost", "")
    with pytest.raises(RuntimeError, match="MCP_AUTH_TOKEN"):
        validate_remote_auth("0.0.0.0", None)
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        validate_remote_auth("::", "too-short")


def test_oauth_can_protect_remote_listener_without_static_secret():
    validate_remote_auth("0.0.0.0", None, oauth_enabled=True)


@pytest.mark.asyncio
async def test_oauth_middleware_passes_bearer_request_to_sdk_verifier():
    app = McpAccessMiddleware(_ok_app, token=None, oauth_enabled=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/mcp", headers={"Authorization": "Bearer opaque-or-jwt"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_oauth_protected_resource_metadata_path_is_forwarded():
    app = McpAccessMiddleware(_ok_app, token=None, oauth_enabled=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/.well-known/oauth-protected-resource")
    assert response.status_code == 200
