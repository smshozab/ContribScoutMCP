"""Auth0-compatible JWT bearer token verification for the OAuth resource server."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken

logger = logging.getLogger(__name__)


class JwtTokenVerifier:
    """Verify Auth0 JWT access tokens against issuer, API audience, expiry, and scopes."""

    def __init__(self, issuer: str, audience: str, required_scopes: list[str]):
        self.issuer = issuer.rstrip("/") + "/"
        self.audience = audience
        self.required_scopes = tuple(required_scopes)
        self.jwks_client = PyJWKClient(f"{self.issuer}.well-known/jwks.json", cache_jwk_set=True)

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = await asyncio.to_thread(self._decode_token, token)
        except (jwt.PyJWTError, jwt.PyJWKClientError, ValueError) as exc:
            logger.info("Rejected invalid OAuth access token (%s)", type(exc).__name__)
            return None

        raw_scopes = claims.get("scope", "")
        scopes = set(raw_scopes.split() if isinstance(raw_scopes, str) else [])
        permissions = claims.get("permissions", [])
        if isinstance(permissions, list):
            scopes.update(item for item in permissions if isinstance(item, str))
        if not set(self.required_scopes).issubset(scopes):
            logger.info("Rejected OAuth token missing required scopes")
            return None

        client_id = claims.get("azp") or claims.get("client_id") or claims.get("sub")
        if not isinstance(client_id, str) or not client_id:
            return None
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=sorted(scopes),
            expires_at=int(claims["exp"]),
            resource=self.audience,
            subject=claims.get("sub") if isinstance(claims.get("sub"), str) else None,
            claims=claims,
        )

    def _decode_token(self, token: str) -> dict[str, Any]:
        signing_key = self.jwks_client.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=self.issuer,
            audience=self.audience,
            options={"require": ["exp", "iat", "iss", "sub", "aud"]},
            leeway=30,
        )
        return claims
