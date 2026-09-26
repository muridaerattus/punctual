"""OAuth resource-server integration; authorization stays with the issuer."""

import asyncio
import secrets

import jwt
from fastmcp.server.auth import AccessToken, RemoteAuthProvider, TokenVerifier
from pydantic import AnyHttpUrl

from ..config import Settings


class MCPTokenVerifier(TokenVerifier):
    def __init__(self, settings: Settings):
        super().__init__(required_scopes=settings.mcp_scopes.split())
        self.settings = settings
        self.keys = jwt.PyJWKClient(settings.mcp_jwks_url, timeout=10)

    async def verify_token(self, token: str) -> AccessToken | None:
        if secrets.compare_digest(token.encode(), self.settings.api_key.encode()):
            return AccessToken(
                token=token, client_id="api-key", scopes=self.required_scopes
            )
        try:
            key = await asyncio.to_thread(self.keys.get_signing_key_from_jwt, token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=self.settings.mcp_issuer,
                audience=self.settings.mcp_resource,
                options={"require": ["iss", "aud", "exp", "iat", "sub"]},
            )
            # Authentik 2026.8 adds uid/azp/scope only in to_access_token(),
            # never in to_jwt(). Do not add these claims through scope mappings.
            if self.settings.mcp_token_profile == "authentik":
                if not all(
                    isinstance(claims.get(k), str) and claims[k]
                    for k in ("uid", "azp", "scope")
                ):
                    return None
            elif jwt.get_unverified_header(token).get("typ") not in (
                "at+jwt",
                "application/at+jwt",
            ):
                return None
            groups = claims.get("groups")
            if not isinstance(groups, list) or self.settings.mcp_group not in groups:
                return None
            if not isinstance(claims.get("sub"), str) or not claims["sub"]:
                return None
            scope = claims.get("scope", "")
            if not isinstance(scope, str):
                return None
            return AccessToken(
                token=token,
                client_id=claims.get("client_id") or claims.get("azp") or claims["sub"],
                subject=claims["sub"],
                scopes=scope.split(),
                expires_at=int(claims["exp"]),
                claims=claims,
            )
        except (jwt.PyJWTError, ValueError, TypeError, OSError):
            return None


class MCPAuth(RemoteAuthProvider):
    def __init__(self, settings: Settings):
        self.resource = AnyHttpUrl(settings.mcp_resource)
        super().__init__(
            token_verifier=MCPTokenVerifier(settings),
            authorization_servers=[AnyHttpUrl(settings.mcp_issuer)],
            base_url=settings.mcp_resource,
            resource_name="Punctual MCP",
        )

    def _get_resource_url(self, path=None):
        # The application mounts the transport separately from root discovery.
        return self.resource
