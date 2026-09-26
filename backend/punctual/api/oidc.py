"""Confidential OIDC login; credentials and opaque sessions stay server-side.

One process only. A restart revokes all sessions and pending authorizations.
No refresh tokens: group removal takes effect by the fixed session deadline.
"""

import hashlib
import secrets
import time
from urllib.parse import urlsplit

import httpx2 as httpx
import jwt
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ..config import Settings

SESSION_COOKIE = "__Host-punctual-session"
FLOW_COOKIE = "__Host-punctual-flow"
PUBLIC_AUTH_PATHS = {
    "/api/auth/session",
    "/api/auth/login",
    "/api/auth/callback",
    "/api/auth/logout",
}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class BrowserAuth:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sessions: dict[str, dict] = {}
        self.flows: dict[str, dict] = {}

    def prune(self):
        now = time.time()
        for store in (self.sessions, self.flows):
            for key in list(store):
                if store[key]["expires"] <= now:
                    del store[key]

    def session(self, request: Request):
        self.prune()
        return self.sessions.get(digest(request.cookies.get(SESSION_COOKIE, "")))

    def revoke(self, request: Request):
        self.sessions.pop(digest(request.cookies.get(SESSION_COOKIE, "")), None)

    def csrf_valid(self, request: Request):
        return (
            request.headers.get("origin") == self.settings.public_url
            and request.headers.get("x-punctual-csrf") == "1"
        )

    async def metadata(self):
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                self.settings.oidc_issuer.rstrip("/")
                + "/.well-known/openid-configuration"
            )
            response.raise_for_status()
            data = response.json()
        if data["issuer"] != self.settings.oidc_issuer:
            raise ValueError("Issuer mismatch")
        for field in (
            "authorization_endpoint",
            "token_endpoint",
            "jwks_uri",
            "end_session_endpoint",
        ):
            url = urlsplit(data[field])
            if (
                url.scheme != "https"
                or not url.netloc
                or url.username
                or url.password
                or url.fragment
            ):
                raise ValueError("Invalid provider endpoint")
        return data

    def client(self):
        return AsyncOAuth2Client(
            client_id=self.settings.oidc_client_id,
            client_secret=self.settings.oidc_client_secret,
            redirect_uri=self.settings.public_url + "/api/auth/callback",
            scope="openid profile email",
            code_challenge_method="S256",
            token_endpoint_auth_method="client_secret_basic",
            timeout=10,
        )

    async def identity(self, token, metadata, nonce):
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(metadata["jwks_uri"])
            response.raise_for_status()
            keys = jwt.PyJWKSet.from_dict(response.json())
        header = jwt.get_unverified_header(token)
        key = keys[header["kid"]]
        if key.key_type != "RSA":
            raise ValueError("RSA signing required")
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=self.settings.oidc_issuer,
            audience=self.settings.oidc_client_id,
            options={"require": ["iss", "sub", "aud", "exp", "iat", "nonce"]},
        )
        if not isinstance(claims["sub"], str) or not claims["sub"]:
            raise ValueError("Missing subject")
        if not isinstance(claims["nonce"], str) or not secrets.compare_digest(
            claims["nonce"], nonce
        ):
            raise ValueError("Nonce mismatch")
        if (
            claims.get("azp", self.settings.oidc_client_id)
            != self.settings.oidc_client_id
        ):
            raise ValueError("Authorized party mismatch")
        if (
            isinstance(claims["aud"], list)
            and len(claims["aud"]) > 1
            and "azp" not in claims
        ):
            raise ValueError("Authorized party required")
        groups = claims.get("groups")
        if not isinstance(groups, list) or self.settings.oidc_group not in groups:
            raise ValueError("Team membership required")
        return claims

    def router(self):
        router = APIRouter(prefix="/api/auth")

        @router.get("/session")
        async def status(request: Request):
            session = self.session(request)
            return {
                "mode": "oidc" if self.settings.oidc_issuer else "bearer",
                "authenticated": bool(session),
            }

        @router.get("/login")
        async def login(request: Request):
            if not self.settings.oidc_issuer:
                return JSONResponse(
                    {"error": {"message": "OIDC is disabled"}}, status_code=404
                )
            self.prune()
            if len(self.flows) >= 1024 or len(self.sessions) >= 4096:
                return JSONResponse(
                    {"error": {"message": "Try signing in later"}}, status_code=503
                )
            try:
                metadata = await self.metadata()
                nonce, verifier, flow = (secrets.token_urlsafe(32) for _ in range(3))
                async with self.client() as client:
                    url, state = client.create_authorization_url(
                        metadata["authorization_endpoint"],
                        nonce=nonce,
                        code_verifier=verifier,
                    )
                self.flows.pop(digest(request.cookies.get(FLOW_COOKIE, "")), None)
                self.flows[digest(flow)] = {
                    "state": state,
                    "nonce": nonce,
                    "verifier": verifier,
                    "expires": time.time() + 300,
                }
                response = RedirectResponse(url, status_code=303)
                response.set_cookie(
                    FLOW_COOKIE,
                    flow,
                    max_age=300,
                    secure=True,
                    httponly=True,
                    samesite="lax",
                )
                return response
            except (httpx.HTTPError, OAuthError, ValueError, KeyError):
                return JSONResponse(
                    {"error": {"message": "Sign-in provider unavailable"}},
                    status_code=503,
                )

        @router.get("/callback")
        async def callback(request: Request):
            self.prune()
            flow = self.flows.pop(digest(request.cookies.get(FLOW_COOKIE, "")), None)
            response = RedirectResponse("/?auth_error=1", status_code=303)
            response.delete_cookie(
                FLOW_COOKIE, secure=True, httponly=True, samesite="lax"
            )
            try:
                if not flow or not secrets.compare_digest(
                    request.query_params.get("state", ""), flow["state"]
                ):
                    return response
                if "error" in request.query_params or not request.query_params.get(
                    "code"
                ):
                    return response
                metadata = await self.metadata()
                async with self.client() as client:
                    token = await client.fetch_token(
                        metadata["token_endpoint"],
                        code=request.query_params["code"],
                        code_verifier=flow["verifier"],
                        grant_type="authorization_code",
                    )
                claims = await self.identity(token["id_token"], metadata, flow["nonce"])
                self.revoke(request)
                session_id = secrets.token_urlsafe(32)
                lifetime = min(
                    self.settings.session_seconds, int(claims["exp"] - time.time())
                )
                if lifetime <= 0 or len(self.sessions) >= 4096:
                    return response
                self.sessions[digest(session_id)] = {
                    "subject": (claims["iss"], claims["sub"]),
                    "expires": time.time() + lifetime,
                    "logout_url": metadata["end_session_endpoint"],
                }
                response.headers["location"] = "/"
                response.set_cookie(
                    SESSION_COOKIE,
                    session_id,
                    max_age=lifetime,
                    secure=True,
                    httponly=True,
                    samesite="lax",
                )
            except (
                httpx.HTTPError,
                OAuthError,
                jwt.PyJWTError,
                ValueError,
                KeyError,
                TypeError,
            ):
                pass  # Never log authorization codes, provider tokens or claims.
            return response

        @router.post("/logout")
        async def logout(request: Request):
            if not self.settings.oidc_issuer or not self.csrf_valid(request):
                return JSONResponse(
                    {"error": {"message": "Invalid logout request"}}, status_code=403
                )
            session = self.session(request)
            self.revoke(request)
            response = JSONResponse(
                {"redirect": session["logout_url"] if session else "/"}
            )
            response.delete_cookie(
                SESSION_COOKIE, secure=True, httponly=True, samesite="lax"
            )
            self.flows.pop(digest(request.cookies.get(FLOW_COOKIE, "")), None)
            response.delete_cookie(
                FLOW_COOKIE, secure=True, httponly=True, samesite="lax"
            )
            return response

        return router
