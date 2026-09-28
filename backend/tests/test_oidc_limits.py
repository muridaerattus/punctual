import asyncio
import time

import httpx
import pytest
from fastapi import FastAPI

from punctual.api import oidc
from punctual.config import Settings


@pytest.fixture
def login_app(monkeypatch):
    browser = oidc.BrowserAuth(
        Settings(
            oidc_issuer="https://identity.example/",
            oidc_client_id="test",
            oidc_client_secret="test",
            oidc_group="Team",
            public_url="https://tasks.example",
        )
    )
    clock = [1000.0]
    monkeypatch.setattr(oidc, "monotonic", lambda: clock[0])
    provider = {"calls": 0, "fail": False}

    async def fetch():
        provider["calls"] += 1
        await asyncio.sleep(0)
        if provider["fail"]:
            raise ValueError("Provider unavailable")
        return {"authorization_endpoint": "https://identity.example/authorize"}

    monkeypatch.setattr(browser, "_fetch_metadata", fetch)
    app = FastAPI()
    app.include_router(browser.router())
    return app, browser, clock, provider


def http_client(app, peer="192.0.2.1"):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=(peer, 1234)),
        base_url="https://tasks.example",
    )


def test_login_peer_throttle_ignores_cookies_and_forwarding_headers(login_app):
    app, browser, clock, provider = login_app

    async def check():
        async with http_client(app) as client:
            for index in range(oidc.LOGIN_PEER_LIMIT + 2):
                client.cookies.clear()
                response = await client.get(
                    "/api/auth/login",
                    headers={
                        "X-Forwarded-For": f"198.51.100.{index}",
                        "Forwarded": f"for=198.51.100.{index}",
                    },
                )
                if index < oidc.LOGIN_PEER_LIMIT:
                    assert response.status_code == 303
                else:
                    assert response.status_code == 429
                    assert response.headers["Retry-After"] == str(oidc.LOGIN_WINDOW)
            assert len(browser.flows) == oidc.LOGIN_PEER_LIMIT
            assert len(browser.login_attempts) == oidc.LOGIN_PEER_LIMIT
            async with http_client(app, "192.0.2.2") as other:
                assert (await other.get("/api/auth/login")).status_code == 303
            clock[0] += oidc.LOGIN_WINDOW
            assert (await client.get("/api/auth/login")).status_code == 303
        assert provider["calls"] == 1

    asyncio.run(check())


def test_global_login_throttle_has_bounded_memory(login_app, monkeypatch):
    app, browser, clock, _ = login_app
    monkeypatch.setattr(oidc, "LOGIN_LIMIT", 4)

    async def login(index):
        async with http_client(app, f"192.0.2.{index}") as client:
            return await client.get("/api/auth/login")

    async def check():
        responses = await asyncio.gather(*(login(i) for i in range(20)))
        assert sum(r.status_code == 303 for r in responses) == oidc.LOGIN_LIMIT
        rejected = [r for r in responses if r.status_code == 429]
        assert len(rejected) == 20 - oidc.LOGIN_LIMIT
        assert all(r.headers["Retry-After"] == "60" for r in rejected)
        assert len(browser.login_attempts) == oidc.LOGIN_LIMIT
        assert len(browser.flows) == oidc.LOGIN_LIMIT
        clock[0] += oidc.LOGIN_WINDOW
        assert (await login(21)).status_code == 303
        assert len(browser.login_attempts) == 1

    asyncio.run(check())


def test_concurrent_logins_cannot_overbook_flow_capacity(login_app, monkeypatch):
    app, browser, _, _ = login_app
    browser.flows = {
        str(i): {"expires": time.time() + 300} for i in range(oidc.FLOW_LIMIT - 1)
    }

    async def check():
        entered, release = asyncio.Event(), asyncio.Event()
        fetch = browser._fetch_metadata

        async def blocked_fetch():
            entered.set()
            await release.wait()
            return await fetch()

        monkeypatch.setattr(browser, "_fetch_metadata", blocked_fetch)
        async with http_client(app) as client:
            first = asyncio.create_task(client.get("/api/auth/login"))
            try:
                await asyncio.wait_for(entered.wait(), 2)
                responses = await asyncio.wait_for(
                    asyncio.gather(*(client.get("/api/auth/login") for _ in range(4))),
                    2,
                )
                assert all(r.status_code == 503 for r in responses)
                assert browser.pending_logins == 1
            finally:
                release.set()
            assert (await first).status_code == 303
            assert browser.pending_logins == 0
            assert len(browser.flows) == oidc.FLOW_LIMIT
            assert (await client.get("/api/auth/login")).status_code == 503

    asyncio.run(check())


def test_cancelled_login_releases_capacity(login_app, monkeypatch):
    app, browser, _, _ = login_app

    async def check():
        entered = asyncio.Event()
        fetch = browser._fetch_metadata

        async def blocked_fetch():
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(browser, "_fetch_metadata", blocked_fetch)
        async with http_client(app) as client:
            request = asyncio.create_task(client.get("/api/auth/login"))
            await asyncio.wait_for(entered.wait(), 2)
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request
            assert browser.pending_logins == 0
            assert browser.flows == {}
            monkeypatch.setattr(browser, "_fetch_metadata", fetch)
            assert (await client.get("/api/auth/login")).status_code == 303
            assert browser.pending_logins == 0

    asyncio.run(check())


def test_provider_failure_backs_off_and_releases_capacity(login_app):
    app, browser, clock, provider = login_app
    provider["fail"] = True

    async def check():
        async with http_client(app) as client:
            responses = await asyncio.gather(
                *(client.get("/api/auth/login") for _ in range(4))
            )
            assert all(r.status_code == 503 for r in responses)
            assert provider["calls"] == 1
            assert browser.pending_logins == 0
            assert browser.flows == {}
            provider["fail"] = False
            clock[0] += oidc.DISCOVERY_RETRY_SECONDS
            assert (await client.get("/api/auth/login")).status_code == 303
            assert provider["calls"] == 2

    asyncio.run(check())


def test_discovery_cache_expiry_coalesces_refreshes(login_app):
    _, browser, clock, provider = login_app

    async def check():
        for expected_calls in (1, 2):
            results = await asyncio.gather(*(browser.metadata() for _ in range(20)))
            assert all(result == results[0] for result in results)
            assert provider["calls"] == expected_calls
            await browser.metadata()
            assert provider["calls"] == expected_calls
            clock[0] += oidc.DISCOVERY_SECONDS

    asyncio.run(check())
