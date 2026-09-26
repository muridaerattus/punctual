import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from punctual.app import create_app
from punctual.mcp.auth import MCPTokenVerifier

ISSUER = "https://identity.example/application/o/mcp/"
RESOURCE = "https://tasks.example/mcp"


@pytest.fixture
def oauth(monkeypatch, tmp_path):
    for name, value in {
        "MCP_ISSUER": ISSUER,
        "MCP_JWKS_URL": ISSUER + "jwks/",
        "MCP_RESOURCE": RESOURCE,
        "MCP_GROUP": "Team",
        "MCP_SCOPES": "tasks:access",
        "MCP_TOKEN_PROFILE": "authentik",
    }.items():
        monkeypatch.setenv("PUNCTUAL_" + name, value)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        "jwt.PyJWKClient.get_signing_key_from_jwt",
        lambda self, token: SimpleNamespace(key=private.public_key()),
    )
    app = create_app(str(tmp_path / "db"), api_key="existing-api-key")
    with TestClient(app) as client:
        yield client, private


def sign(key, **changes):
    claims = {
        "iss": ISSUER,
        "aud": RESOURCE,
        "sub": "user-1",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
        "groups": ["Team"],
        "scope": "tasks:access",
        "uid": "access-token-only",
        "azp": "desktop-client",
    }
    claims.update(changes)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256")


def rpc(client, token=None):
    headers = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": "tools/list",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    return client.post(
        "/mcp/",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                }
            },
        },
    )


def test_metadata_challenge_and_compatibility(oauth):
    client, key = oauth
    metadata = client.get("/.well-known/oauth-protected-resource/mcp")
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == RESOURCE
    assert metadata.json()["authorization_servers"] == [ISSUER]
    assert metadata.json()["scopes_supported"] == ["tasks:access"]
    response = rpc(client)
    assert response.status_code == 401
    assert (
        'resource_metadata="https://tasks.example/.well-known/oauth-protected-resource/mcp"'
        in response.headers["WWW-Authenticate"]
    )
    assert 'scope="tasks:access"' in response.headers["WWW-Authenticate"]
    for token in (sign(key), "existing-api-key"):
        response = rpc(client, token)
        assert response.status_code == 200
        assert response.json()["result"]["tools"]
    assert (
        client.get(
            "/api/boards", headers={"Authorization": "Bearer " + sign(key)}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/boards", headers={"Authorization": "Bearer existing-api-key"}
        ).status_code
        == 200
    )
    assert rpc(client, "invalid").status_code == 401


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": 1},
        {"exp": None},
        {"iss": "https://wrong.example/"},
        {"aud": "browser-client"},
        {"groups": ["Other"]},
        {"groups": "Team"},
        {"uid": None},
        {"azp": None},
        {"sub": None},
        {"nbf": int(time.time()) + 600},
    ],
)
def test_reject_invalid_tokens(oauth, claims):
    client, key = oauth
    assert rpc(client, sign(key, **claims)).status_code == 401


def test_scope_and_signature(oauth):
    client, key = oauth
    assert rpc(client, sign(key, scope="unrelated")).status_code == 403
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert rpc(client, sign(other)).status_code == 401
    assert rpc(client, sign(key, uid=None, azp=None, scope=None)).status_code == 401


def test_browser_cookie_never_authorizes_mcp(oauth):
    from punctual.api.oidc import SESSION_COOKIE, digest

    client, _ = oauth
    client.app.state.browser_auth.sessions[digest("browser-session")] = {
        "expires": time.time() + 60
    }
    client.cookies.set(SESSION_COOKIE, "browser-session")
    assert client.get("/api/boards").status_code == 200
    assert rpc(client).status_code == 401


def test_rfc9068_profile(oauth):
    import asyncio

    from punctual.config import Settings

    _, key = oauth
    verifier = MCPTokenVerifier(Settings(mcp_token_profile="rfc9068"))
    token = sign(key)
    assert asyncio.run(verifier.verify_token(token)) is None
    claims = jwt.decode(
        token, key.public_key(), algorithms=["RS256"], audience=RESOURCE
    )
    access = jwt.encode(claims, key, algorithm="RS256", headers={"typ": "at+jwt"})
    assert asyncio.run(verifier.verify_token(access)) is not None
