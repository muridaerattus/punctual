import json

import httpx
import pytest
from typer.testing import CliRunner

from punctual.cli.app import app
from punctual.cli.diagnostics import TOOLS, VERSION, diagnose


def test_doctor_against_app(client, monkeypatch):
    def request(method, url, **kwargs):
        kwargs.pop("timeout")
        return client.request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "request", request)
    result = CliRunner().invoke(
        app, ["--url", "http://testserver", "--api-key", "secret", "--json", "doctor"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["ok"]
    assert "secret" not in result.output
    assert (
        client.get("/api/tasks", headers={"Authorization": "Bearer secret"}).json()
        == []
    )


@pytest.mark.parametrize(
    "status,code",
    [(401, "unauthorized"), (405, "wrong_endpoint"), (421, "disallowed_host")],
)
def test_doctor_sanitizes_errors(monkeypatch, status, code):
    monkeypatch.setattr(
        httpx, "request", lambda *a, **kw: httpx.Response(status, text="secret")
    )
    result = diagnose("http://example", "secret")
    assert result["error"]["code"] == code
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize(
    "versions,tools,code",
    [
        (["2025-11-25"], TOOLS, "unsupported_protocol"),
        ([VERSION], {"list_tasks"}, "missing_tools"),
        ([VERSION], TOOLS, None),
    ],
)
def test_discovery_and_catalog(monkeypatch, versions, tools, code):
    def request(method, url, **kwargs):
        assert kwargs["headers"]["Host"] == "localhost:8000"
        if method == "GET":
            return httpx.Response(200)
        rpc = kwargs["json"]
        assert (
            rpc["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] == VERSION
        )
        result = (
            {"supportedVersions": versions}
            if rpc["method"] == "server/discover"
            else {"tools": [{"name": name} for name in tools]}
        )
        return httpx.Response(200, json={"result": result})

    monkeypatch.setattr(httpx, "request", request)
    result = diagnose("http://127.0.0.1:8000", "secret", "localhost:8000")
    assert result.get("error", {}).get("code") == code
    assert result["ok"] == (code is None)


def test_network_error_does_not_echo_exception(monkeypatch):
    def request(*args, **kwargs):
        raise httpx.ConnectError("secret")

    monkeypatch.setattr(httpx, "request", request)
    result = diagnose("http://example", "secret")
    assert result["error"]["code"] == "connection_failed"
    assert "secret" not in json.dumps(result)
