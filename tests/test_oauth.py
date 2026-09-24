import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from contribscout.app.config import Settings
from contribscout.app.oauth import JwtTokenVerifier


class _SigningKey:
    def __init__(self, key):
        self.key = key


def test_oauth_configuration_requires_all_resource_server_values():
    with pytest.raises(ValueError, match="Configure MCP_OAUTH"):
        Settings(mcp_oauth_issuer_url="https://tenant.auth0.com/")


def test_oauth_configuration_accepts_full_auth0_resource_settings():
    settings = Settings(
        mcp_oauth_issuer_url="https://tenant.auth0.com/",
        mcp_oauth_resource_url="https://contribscout.example/mcp",
        mcp_oauth_audience="https://contribscout.example/mcp",
    )
    assert settings.oauth_enabled
    assert settings.mcp_oauth_required_scopes == ["contribscout:read"]


def test_auth0_audience_must_match_normalized_resource_url():
    with pytest.raises(ValueError, match="must exactly match"):
        Settings(
            mcp_oauth_issuer_url="https://tenant.auth0.com/",
            mcp_oauth_resource_url="https://contribscout.example",
            mcp_oauth_audience="https://contribscout.example",
        )


@pytest.mark.asyncio
async def test_jwt_verifier_rejects_tokens_missing_required_scope(monkeypatch):
    verifier = JwtTokenVerifier("https://tenant.auth0.com/", "https://contribscout.example/mcp", ["contribscout:read"])
    monkeypatch.setattr(
        verifier,
        "_decode_token",
        lambda token: {
            "sub": "user-123",
            "azp": "client-123",
            "iss": "https://tenant.auth0.com/",
            "aud": "https://contribscout.example/mcp",
            "iat": 1,
            "exp": 4_000_000_000,
            "scope": "openid profile",
        },
    )
    assert await verifier.verify_token("signed.jwt.token") is None


@pytest.mark.asyncio
async def test_jwt_verifier_returns_scoped_access_token(monkeypatch):
    verifier = JwtTokenVerifier("https://tenant.auth0.com/", "https://contribscout.example/mcp", ["contribscout:read"])
    monkeypatch.setattr(
        verifier,
        "_decode_token",
        lambda token: {
            "sub": "auth0|user-123",
            "azp": "client-123",
            "iss": "https://tenant.auth0.com/",
            "aud": "https://contribscout.example/mcp",
            "iat": 1,
            "exp": 4_000_000_000,
            "scope": "openid contribscout:read",
        },
    )
    access_token = await verifier.verify_token("signed.jwt.token")
    assert access_token is not None
    assert access_token.client_id == "client-123"
    assert access_token.subject == "auth0|user-123"
    assert "contribscout:read" in access_token.scopes


@pytest.mark.asyncio
async def test_jwt_verifier_checks_signature_issuer_audience_and_expiry(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = JwtTokenVerifier("https://tenant.auth0.com/", "https://contribscout.example/mcp", ["contribscout:read"])
    monkeypatch.setattr(verifier.jwks_client, "get_signing_key_from_jwt", lambda _: _SigningKey(private_key.public_key()))

    claims = {
        "sub": "auth0|user-123",
        "azp": "client-123",
        "iss": "https://tenant.auth0.com/",
        "aud": "https://contribscout.example/mcp",
        "iat": 1_700_000_000,
        "exp": 2_000_000_000,
        "scope": "contribscout:read",
    }
    valid_token = jwt.encode(claims, private_key, algorithm="RS256")
    assert await verifier.verify_token(valid_token) is not None

    wrong_audience = {**claims, "aud": "https://another-resource.example/"}
    invalid_token = jwt.encode(wrong_audience, private_key, algorithm="RS256")
    assert await verifier.verify_token(invalid_token) is None

    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    invalid_signature = jwt.encode(claims, wrong_key, algorithm="RS256")
    assert await verifier.verify_token(invalid_signature) is None
