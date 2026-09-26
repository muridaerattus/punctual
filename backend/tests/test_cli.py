import json

import httpx
import pytest
from typer.testing import CliRunner

from punctual.cli.app import app


@pytest.fixture
def cli(client, monkeypatch):
    requests = []

    def request(method, url, **kwargs):
        requests.append((method, url, kwargs))
        kwargs.pop("timeout", None)
        return client.request(method, url, **kwargs)

    monkeypatch.setattr(httpx, "request", request)
    runner = CliRunner()

    def command(*args, exit_code=0):
        result = runner.invoke(
            app, ["--api-key", "secret", "--url", "http://testserver", "--json", *args]
        )
        assert result.exit_code == exit_code, result.output
        return json.loads(result.output)

    command.requests = requests
    return command


def test_cli_http_workflow(cli):
    command = cli
    task = command("create", "CLI task", "--assignee", "agent")
    task_id = str(task["id"])
    assert command("list", "--assignee", "agent")[0]["id"] == task["id"]
    lease = command("claim", task_id, "cli-agent")
    assert (
        command(
            "update", task_id, "--revision", "1", "--status", "Complete", exit_code=3
        )["error"]["code"]
        == "task_locked"
    )
    token_args = ["--lease-token", lease["lease_token"]]
    assert (
        command("update", task_id, "--revision", "1", "--clear-assignee", *token_args)[
            "assignee"
        ]
        is None
    )
    command("renew", task_id, *token_args)
    command("release", task_id, *token_args)
    assert command("get", task_id)["revision"] == 2
    assert command("delete", task_id, "--revision", "2")["deleted"] == task["id"]


def test_cli_boards_and_parent_keys(cli):
    default = cli("create", "Default task")
    board = cli("boards", "create", "Engineering", "--prefix", "ENG")
    assert board == {"id": 2, "name": "Engineering", "prefix": "ENG"}
    assert cli("boards", "list") == [
        {"id": 1, "name": "Default", "prefix": "PUN"},
        board,
    ]
    parent = cli("create", "Parent", "--board", "ENG", "--assignee", "agent")
    assert parent["key"] == "ENG-1"
    assert parent["id"] != parent["number"]
    assert cli("get", "ENG-1") == parent
    assert cli("get", str(parent["id"])) == parent
    assert cli("list") == [default]
    assert cli("list", "--board", "2", "--query", "ENG-1") == [parent]
    assert cli("list", "--board", "ENG", "--assignee", "agent") == [parent]
    assert cli("list", "--board", "ENG", "--status", "Complete") == []
    child = cli("create", "Child", "--board", "2", "--parent-id", "ENG-1")
    assert child["parent_id"] == parent["id"]
    assert child["parent_key"] == "ENG-1"
    detached = cli("update", child["key"], "--revision", "1", "--clear-parent")
    assert detached["parent_id"] is None
    attached = cli("update", child["key"], "--revision", "2", "--parent-id", "ENG-1")
    assert attached["parent_id"] == parent["id"]
    # Selecting a parent must not implicitly change the default board.
    error = cli("create", "Wrong board", "--parent-id", "ENG-1", exit_code=1)
    assert error["error"]["code"] == "invalid_parent"
    assert cli("list") == [default]

    numeric_child = cli(
        "create", "Numeric parent", "--board", "ENG", "--parent-id", str(parent["id"])
    )
    assert numeric_child["parent_id"] == parent["id"]
    assert (
        cli(
            "update",
            str(numeric_child["id"]),
            "--revision",
            "1",
            "--parent-id",
            str(parent["id"]),
        )["parent_id"]
        == parent["id"]
    )


def test_cli_key_leases_and_stale_writes(cli):
    cli("create", "Default task")
    cli("boards", "create", "Engineering", "--prefix", "ENG")
    task = cli("create", "Task", "--board", "ENG")
    key = task["key"]
    token = "a" * 32
    token_args = ["--lease-token", token]
    lease = cli("claim", key, "agent", *token_args)
    assert lease["id"] == task["id"]
    assert lease["lease_token"] == token
    assert cli("claim", key, "agent", *token_args)["lease_id"] == lease["lease_id"]
    assert cli("renew", key, "--seconds", "1200", *token_args)["lease_owner"] == "agent"
    assert cli("update", key, "--revision", "1", exit_code=3)["error"]["code"] == (
        "task_locked"
    )
    changed = cli("update", key, "--revision", "1", "--status", "Complete", *token_args)
    assert changed["revision"] == 2
    for command in ("update", "delete"):
        cli.requests.clear()
        error = cli(command, key, "--revision", "1", *token_args, exit_code=3)
        assert error["error"]["code"] == "revision_conflict"
        # One identity lookup, one write with the caller's revision; no retry.
        assert [r[0] for r in cli.requests] == [
            "GET",
            "PATCH" if command == "update" else "DELETE",
        ]
        assert cli.requests[1][1].endswith(f"/api/tasks/{task['id']}")
        assert cli.requests[1][2]["json"]["revision"] == 1
        assert cli.requests[1][2]["json"]["lease_token"] == token
    cli("release", key, *token_args)
    assert cli("get", key)["lease_owner"] is None
    assert cli("delete", key, "--revision", "2")["deleted"] == task["id"]


def test_cli_key_force_release_and_history(cli):
    task = cli("create", "Task")
    lease = cli("claim", task["key"], "agent")
    cli(
        "force-release",
        task["key"],
        "--revision",
        "1",
        "--lease-id",
        lease["lease_id"],
        "--reason",
        "Lost token",
    )
    history = cli("lease-history", task["key"])
    assert len(history) == 1
    assert history[0]["reason"] == "Lost token"
    current = cli("get", task["key"])
    cli("delete", task["key"], "--revision", str(current["revision"]))
    # Numeric IDs still allow audit lookup after deletion (keys need a live task).
    assert cli("lease-history", str(task["id"])) == history


def test_cli_board_and_key_errors(cli):
    cli("boards", "create", "Engineering", "--prefix", "ENG")
    assert (
        cli("boards", "create", "Duplicate", "--prefix", "ENG", exit_code=3)["error"][
            "code"
        ]
        == "prefix_conflict"
    )
    assert (
        cli("boards", "create", "Invalid", "--prefix", "lowercase", exit_code=1)[
            "error"
        ]["code"]
        == "validation_error"
    )
    for board in ("UNKNOWN", "999"):
        assert (
            cli("list", "--board", board, exit_code=1)["error"]["code"] == "not_found"
        )
        assert (
            cli("create", "Task", "--board", board, exit_code=1)["error"]["code"]
            == "not_found"
        )
    for key, code in (("ENG-999", "not_found"), ("invalid", "invalid_key")):
        cli.requests.clear()
        assert (
            cli("update", key, "--revision", "1", exit_code=1)["error"]["code"] == code
        )
        assert [r[0] for r in cli.requests] == ["GET"]
    assert cli("list", "--board", "ENG") == []


def test_cli_key_writes_require_explicit_revision(cli):
    runner = CliRunner()
    for command in ("update", "delete"):
        result = runner.invoke(app, [command, "PUN-1"])
        assert result.exit_code == 2
        assert not cli.requests


@pytest.mark.parametrize(
    "args",
    [
        ["list", "--board", "ENG"],
        ["update", "ENG-1", "--revision", "1"],
        ["boards", "list"],
    ],
)
def test_cli_lookup_auth_errors(cli, args):
    result = CliRunner().invoke(
        app, ["--api-key", "wrong", "--url", "http://testserver", "--json", *args]
    )
    assert result.exit_code == 1
    assert "error" in json.loads(result.output)
    assert [r[0] for r in cli.requests] == ["GET"]
