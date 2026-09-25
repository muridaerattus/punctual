import json

import httpx
from typer.testing import CliRunner

from punctual.cli.app import app


def test_cli_http_workflow(client, monkeypatch):
    def request(method, url, **kwargs):
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
