import json
import secrets
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from typer.testing import CliRunner

from punctual.cli.app import app
from punctual.tasks.errors import Conflict
from punctual.tasks.schemas import ForceReleaseInput, TaskInput, TaskPatch
from punctual.tasks.service import TaskService


def test_recover_claim_after_lost_response_and_restart(store):
    task = store.create(TaskInput(title="Recoverable"))
    token = secrets.token_urlsafe(32)
    first = store.lease(task["id"], "claim", owner="agent", token=token)
    restarted = TaskService(store.path)
    try:
        recovered = restarted.lease(
            task["id"], "claim", owner="agent", token=token, seconds=3600
        )
        assert recovered == first
        assert "lease_token" not in restarted.get(task["id"])
        assert "lease_token" not in restarted.list()[0]
        for owner, candidate in [
            ("other", token),
            ("agent", secrets.token_urlsafe(32)),
        ]:
            with pytest.raises(Conflict, match="claimed"):
                restarted.lease(task["id"], "claim", owner=owner, token=candidate)
        assert (
            restarted.update(
                task["id"], TaskPatch(revision=1, lease_token=token, status="Complete")
            )["status"]
            == "Complete"
        )
    finally:
        restarted.database.engine.dispose()


def test_force_release_is_atomic_and_audited(store):
    task = store.create(TaskInput(title="Lost token"))
    lease = store.lease(task["id"], "claim", owner="agent")
    release = ForceReleaseInput(
        revision=1, lease_id=lease["lease_id"], reason="Lost claim response"
    )

    def force():
        try:
            return store.force_release(task["id"], release)
        except Conflict as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: force(), range(2)))
    assert outcomes.count("lease_conflict") == 1
    assert len(store.lease_history(task["id"])) == 1
    assert store.get(task["id"])["lease_id"] is None
    for action in ("renew", "release"):
        with pytest.raises(Conflict):
            store.lease(task["id"], action, token=lease["lease_token"])
    new = store.lease(task["id"], "claim", owner="agent")
    assert new["lease_id"] != lease["lease_id"]
    with pytest.raises(Conflict, match="Lease changed"):
        store.force_release(task["id"], release)
    store.lease(task["id"], "release", token=new["lease_token"])
    store.delete(task["id"], 1)
    restarted = TaskService(store.path)
    try:
        events = restarted.lease_history(task["id"])
        assert events[0]["reason"] == "Lost claim response"
        assert events[0]["lease_id"] == lease["lease_id"]
        assert lease["lease_token"] not in json.dumps(events)
    finally:
        restarted.database.engine.dispose()


def test_force_release_rejects_stale_revision(store):
    task = store.create(TaskInput(title="Updated"))
    lease = store.lease(task["id"], "claim", owner="agent")
    store.update(
        task["id"], TaskPatch(revision=1, lease_token=lease["lease_token"], title="New")
    )
    with pytest.raises(Conflict, match="Task changed"):
        store.force_release(
            task["id"],
            ForceReleaseInput(
                revision=1, lease_id=lease["lease_id"], reason="Stale view"
            ),
        )
    assert store.lease_history(task["id"]) == []
    assert store.get(task["id"])["lease_id"] == lease["lease_id"]


def test_force_release_auth_validation_and_cli(client, auth, monkeypatch):
    task = client.post(
        "/api/tasks", headers=auth, json={"title": "CLI recovery"}
    ).json()
    token = secrets.token_urlsafe(32)

    def request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        return client.request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "request", request)
    runner = CliRunner()

    def cli(*args):
        result = runner.invoke(
            app, ["--url", "http://testserver", "--api-key", "secret", "--json", *args]
        )
        assert result.exit_code == 0, result.output
        return json.loads(result.output)

    lease = cli("claim", str(task["id"]), "cli", "--lease-token", token)
    assert cli("claim", str(task["id"]), "cli", "--lease-token", token) == lease
    path = f"/api/tasks/{task['id']}/force-release"
    body = {"revision": 1, "lease_id": lease["lease_id"], "reason": "Lost token"}
    assert client.post(path, json=body).status_code == 401
    assert (
        client.post(path, headers=auth, json={**body, "reason": " "}).status_code == 422
    )
    released = cli(
        "force-release",
        str(task["id"]),
        "--revision",
        "1",
        "--lease-id",
        lease["lease_id"],
        "--reason",
        "Lost token",
    )
    assert released["lease_owner"] is None
    assert cli("lease-history", str(task["id"]))[0]["reason"] == "Lost token"


@pytest.mark.parametrize("token", ["é" * 32, "\ud800"])
@pytest.mark.parametrize("action", ["claim", "renew", "release", "update", "delete"])
def test_malformed_tokens_are_rejected_by_http_and_mcp(client, auth, token, action):
    task = client.post("/api/tasks", headers=auth, json={"title": "Protected"}).json()
    path = f"/api/tasks/{task['id']}"
    client.post(path + "/claim", headers=auth, json={"owner": "owner"})
    before = client.get(path, headers=auth).json()
    body = {"lease_token": token}
    if action == "claim":
        body["owner"] = "intruder"
    if action in ("update", "delete"):
        body["revision"] = 1
    if action == "update":
        body["title"] = "Tampered"
    method = {"update": "PATCH", "delete": "DELETE"}.get(action, "POST")
    endpoint = path if action in ("update", "delete") else path + "/" + action
    expected_code = (
        "invalid_token"
        if action == "claim"
        else "task_locked"
        if action in ("update", "delete")
        else "invalid_lease"
    )
    response = client.request(
        method,
        endpoint,
        headers={**auth, "Content-Type": "application/json"},
        content=json.dumps(body),
    )
    schema_rejection = action == "update" and token == "\ud800"
    if schema_rejection:
        assert response.status_code == 422
        assert response.json()["detail"][0]["type"] == "string_unicode"
    else:
        assert response.status_code == (422 if action == "claim" else 409)
        assert response.json()["error"]["code"] == expected_code
    assert client.get(path, headers=auth).json() == before

    tool = {
        "claim": "claim_task",
        "renew": "renew_lease",
        "release": "release_lease",
        "update": "update_task",
        "delete": "delete_task",
    }[action]
    arguments = {"task_id": task["id"]}
    arguments.update({"changes": body} if action == "update" else body)
    response = client.post(
        "/mcp/",
        headers={
            **auth,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": "tools/call",
            "Mcp-Name": tool,
        },
        content=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool,
                    "arguments": arguments,
                    "_meta": {
                        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                        "io.modelcontextprotocol/clientCapabilities": {},
                    },
                },
            }
        ),
    )
    assert response.status_code == 200
    result = response.json()["result"]
    if schema_rejection:
        assert result["isError"] is True
    else:
        assert result["structuredContent"]["ok"] is False
        assert result["structuredContent"]["error"]["code"] == expected_code
    assert client.get(path, headers=auth).json() == before
