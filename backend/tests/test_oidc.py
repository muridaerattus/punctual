import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit

import httpx2 as httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import ValidationError

from punctual.api.oidc import FLOW_COOKIE, SESSION_COOKIE
from punctual.app import create_app
from punctual.config import Settings

ORIGIN = "https://punctual.example"
ISSUER = "https://auth.example/application/o/punctual/"
CSRF = {"Origin": ORIGIN, "X-Punctual-CSRF": "1"}
BEARER = {"Authorization": "Bearer secret"}


@pytest.fixture
def oidc(tmp_path, monkeypatch):
    for key, value in {
        "OIDC_ISSUER": ISSUER,
        "OIDC_CLIENT_ID": "punctual",
        "OIDC_CLIENT_SECRET": "confidential-test-secret",
        "OIDC_GROUP": "Example Team",
        "PUBLIC_URL": ORIGIN,
    }.items():
        monkeypatch.setenv("PUNCTUAL_" + key, value)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update(kid="key1", use="sig", alg="RS256")
    provider = {"overrides": {}, "requests": [], "private": private, "jwk": jwk}

    async def send(client, request, **kwargs):
        provider["requests"].append(request)
        if request.url.path.endswith("openid-configuration"):
            body = {
                "issuer": provider.get("issuer", ISSUER),
                "authorization_endpoint": "https://auth.example/authorize",
                "token_endpoint": "https://auth.example/token",
                "jwks_uri": "https://auth.example/keys",
                "end_session_endpoint": "https://auth.example/logout",
            }
        elif request.url.path == "/keys":
            body = {"keys": [jwk]}
        elif request.url.path == "/token":
            if provider.get("token_error"):
                return httpx.Response(
                    400, json={"error": "invalid_grant"}, request=request
                )
            fields = parse_qs(request.content.decode())
            challenge = (
                base64.urlsafe_b64encode(
                    hashlib.sha256(fields["code_verifier"][0].encode()).digest()
                )
                .rstrip(b"=")
                .decode()
            )
            assert challenge == provider["authorize"]["code_challenge"][0]
            assert fields["redirect_uri"] == [ORIGIN + "/api/auth/callback"]
            assert fields["grant_type"] == ["authorization_code"]
            assert (
                base64.b64decode(request.headers["authorization"].split()[1])
                == b"punctual:confidential-test-secret"
            )
            claims = {
                "iss": ISSUER,
                "aud": "punctual",
                "sub": "stable-user",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
                "nonce": provider["authorize"]["nonce"][0],
                "groups": ["Example Team"],
                **provider["overrides"],
            }
            for field in provider.get("missing", []):
                claims.pop(field)
            token = jwt.encode(
                claims,
                provider.get("signer", private),
                algorithm="RS256",
                headers={"kid": "key1"},
            )
            body = {
                "access_token": "not-for-browser",
                "token_type": "Bearer",
                "id_token": token,
            }
        else:
            raise AssertionError("Unexpected provider request")
        return httpx.Response(200, json=body, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "_send_single_request", send)
    app = create_app(str(tmp_path / "oidc.db"), "secret")
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        yield client, provider, app


def start(client, provider):
    response = client.get("/api/auth/login?next=https://evil.example")
    assert response.status_code == 303
    authorize = parse_qs(urlsplit(response.headers["location"]).query)
    assert authorize["code_challenge_method"] == ["S256"]
    assert authorize["response_type"] == ["code"]
    assert "client_secret" not in authorize
    provider["authorize"] = authorize
    return authorize["state"][0]


def finish(client, state):
    return client.get(
        "/api/auth/callback", params={"state": state, "code": "single-use-code"}
    )


def test_member_login_csrf_logout_and_bearer_mcp(oidc):
    client, provider, app = oidc
    assert client.get("/api/boards").status_code == 401
    assert (
        client.get(
            "/api/boards", headers={"X-Forwarded-User": "admin", "Remote-User": "admin"}
        ).status_code
        == 401
    )
    state = start(client, provider)
    response = finish(client, state)
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "not-for-browser" not in response.text + cookie
    assert client.get("/api/auth/session").json() == {
        "mode": "oidc",
        "authenticated": True,
    }
    assert client.get("/api/boards").status_code == 200
    assert (
        client.get(
            "/api/boards", headers={"Authorization": "Bearer forged"}
        ).status_code
        == 401
    )
    for headers in (
        {},
        {"Origin": "https://evil.example", "X-Punctual-CSRF": "1"},
        {"Origin": ORIGIN},
    ):
        assert (
            client.post(
                "/api/boards", json={"name": "Blocked", "prefix": "NO"}, headers=headers
            ).status_code
            == 403
        )
        assert client.post("/api/auth/logout", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/boards", json={"name": "Team", "prefix": "TEAM"}, headers=CSRF
        ).status_code
        == 201
    )
    rpc = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    assert client.post("/mcp/", json=rpc).status_code == 401
    response = client.post(
        "/mcp/",
        json=rpc,
        headers={
            **BEARER,
            "Accept": "application/json, text/event-stream",
            "Host": "localhost",
        },
    )
    assert response.status_code == 200 and "result" in response.json()
    old_cookie = client.cookies.get(SESSION_COOKIE)
    assert client.post("/api/auth/logout", headers=CSRF).json() == {
        "redirect": "https://auth.example/logout"
    }
    assert client.get("/api/boards").status_code == 401
    client.cookies.set(SESSION_COOKIE, old_cookie)
    assert client.get("/api/boards").status_code == 401
    assert client.get("/api/boards", headers=BEARER).status_code == 200
    assert not app.state.browser_auth.sessions


@pytest.mark.parametrize(
    "overrides,missing",
    [
        ({"iss": "https://evil.example/"}, []),
        ({"aud": "other-client"}, []),
        ({"exp": 1}, []),
        ({"iat": 9999999999}, []),
        ({"nonce": "forged"}, []),
        ({"groups": []}, []),
        ({"groups": "Example Team"}, []),
        ({"groups": ["Other Team"]}, []),
        ({"azp": "other-client"}, []),
        ({"aud": ["punctual", "other"]}, []),
        ({}, ["nonce"]),
        ({}, ["exp"]),
        ({}, ["groups"]),
    ],
)
def test_reject_invalid_identity(oidc, overrides, missing):
    client, provider, _ = oidc
    provider.update(overrides=overrides, missing=missing)
    response = finish(client, start(client, provider))
    assert response.headers["location"] == "/?auth_error=1"
    assert client.get("/api/boards").status_code == 401


def test_signature_state_replay_and_exchange_failures(oidc):
    client, provider, app = oidc
    state = start(client, provider)
    assert finish(client, "wrong").headers["location"] == "/?auth_error=1"
    assert not any(r.url.path == "/token" for r in provider["requests"])
    assert finish(client, state).headers["location"] == "/?auth_error=1"
    state = start(client, provider)
    client.cookies.delete(FLOW_COOKIE)
    assert finish(client, state).headers["location"] == "/?auth_error=1"
    state = start(client, provider)
    provider["signer"] = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert finish(client, state).headers["location"] == "/?auth_error=1"
    provider.pop("signer")
    provider["token_error"] = True
    assert (
        finish(client, start(client, provider)).headers["location"] == "/?auth_error=1"
    )
    provider.pop("token_error")
    state = start(client, provider)
    assert finish(client, state).headers["location"] == "/"
    assert finish(client, state).headers["location"] == "/?auth_error=1"
    for session in app.state.browser_auth.sessions.values():
        session["expires"] = 1
    assert client.get("/api/boards").status_code == 401


def test_provider_mismatch_expired_flow_and_restart(oidc):
    client, provider, app = oidc
    provider["issuer"] = "https://evil.example"
    assert client.get("/api/auth/login").status_code == 503
    provider.pop("issuer")
    state = start(client, provider)
    for flow in app.state.browser_auth.flows.values():
        flow["expires"] = 1
    assert finish(client, state).headers["location"] == "/?auth_error=1"
    assert finish(client, start(client, provider)).headers["location"] == "/"
    from punctual.api.oidc import BrowserAuth

    assert not BrowserAuth(app.state.browser_auth.settings).sessions


def test_bearer_only_mode_and_config(client):
    assert client.get("/api/auth/session").json() == {
        "mode": "bearer",
        "authenticated": False,
    }
    assert client.get("/api/auth/login").status_code == 404
    assert client.get("/api/boards", headers=BEARER).status_code == 200
    with pytest.raises(ValidationError):
        Settings(oidc_issuer=ISSUER)
    with pytest.raises(ValidationError):
        Settings(
            oidc_issuer=ISSUER,
            oidc_client_id="x",
            oidc_client_secret="x",
            public_url="http://insecure.example",
            oidc_group="Example Team",
        )


@pytest.mark.parametrize("group", [None, "", "   "])
def test_oidc_requires_explicit_group(monkeypatch, group):
    monkeypatch.delenv("PUNCTUAL_OIDC_GROUP", raising=False)
    settings = {
        "oidc_issuer": ISSUER,
        "oidc_client_id": "punctual",
        "oidc_client_secret": "secret",
        "public_url": ORIGIN,
    }
    if group is not None:
        settings["oidc_group"] = group
    with pytest.raises(ValidationError, match="required group"):
        Settings(**settings)
