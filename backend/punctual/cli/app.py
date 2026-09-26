"""Commands for humans and automation. All writes use the HTTP API."""

from typing import Annotated

import typer

from .client import Client
from .diagnostics import diagnose

app = typer.Typer(no_args_is_help=True)
boards_app = typer.Typer(no_args_is_help=True, help="Discover and create boards.")
app.add_typer(boards_app, name="boards")


@app.callback()
def options(
    ctx: typer.Context,
    url: str = typer.Option("http://localhost:8000", envvar="PUNCTUAL_URL"),
    api_key: str = typer.Option("", envvar="PUNCTUAL_API_KEY"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Punctual: small, keyboard-friendly task tracking."""
    ctx.obj = Client(url, api_key, json_output)


@app.command()
def doctor(ctx: typer.Context, host: str | None = None):
    """Check health, bearer authentication, MCP discovery and tools without writes.

    --host overrides the HTTP Host header for deployment checks.
    """
    result = diagnose(ctx.obj.url, ctx.obj.api_key, host)
    ctx.obj.emit(result)
    if not result["ok"]:
        raise typer.Exit(1)


@app.command("list")
def list_tasks(
    ctx: typer.Context,
    status: str | None = None,
    assignee: str | None = None,
    query: str | None = None,
    board: str = typer.Option("1", help="Board ID or uppercase prefix."),
):
    filters = {
        "status": status,
        "assignee": assignee,
        "query": query,
        "board_id": ctx.obj.board_id(board),
    }
    ctx.obj.request(
        "GET",
        "",
        params={key: value for key, value in filters.items() if value is not None},
    )


@app.command()
def get(ctx: typer.Context, task_id: str):
    """Get a task by numeric ID or ticket key (for example PUN-13)."""
    ctx.obj.request("GET", ctx.obj.task_path(task_id))


@boards_app.command("list")
def list_boards(ctx: typer.Context):
    ctx.obj.request("GET", "", resource="boards")


@boards_app.command("create")
def create_board(ctx: typer.Context, name: str, prefix: Annotated[str, typer.Option()]):
    """Create a board with a unique prefix of 1–8 uppercase ASCII letters."""
    ctx.obj.request(
        "POST", "", resource="boards", json={"name": name, "prefix": prefix}
    )


@app.command()
def create(
    ctx: typer.Context,
    title: str,
    description: str = "",
    status: str = "To Do",
    assignee: str | None = None,
    parent_id: str | None = None,
    board: str = typer.Option("1", help="Board ID or uppercase prefix."),
):
    ctx.obj.request(
        "POST",
        "",
        json={
            "title": title,
            "description": description,
            "status": status,
            "assignee": assignee,
            "parent_id": ctx.obj.task_id(parent_id) if parent_id is not None else None,
            "board_id": ctx.obj.board_id(board),
        },
    )


@app.command()
def update(
    ctx: typer.Context,
    task_id: str,
    revision: Annotated[int, typer.Option()],
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
    parent_id: str | None = None,
    clear_assignee: bool = False,
    clear_parent: bool = False,
    lease_token: str | None = typer.Option(None, envvar="PUNCTUAL_LEASE_TOKEN"),
):
    changes = {
        "revision": revision,
        "title": title,
        "description": description,
        "status": status,
        "assignee": assignee,
        "parent_id": parent_id,
        "lease_token": lease_token,
    }
    body = {key: value for key, value in changes.items() if value is not None}
    if clear_assignee:
        body["assignee"] = None
    if clear_parent:
        body["parent_id"] = None
    elif parent_id is not None:
        body["parent_id"] = ctx.obj.task_id(parent_id)
    ctx.obj.request("PATCH", f"/{ctx.obj.task_id(task_id)}", json=body)


@app.command()
def delete(
    ctx: typer.Context,
    task_id: str,
    revision: Annotated[int, typer.Option()],
    lease_token: str | None = typer.Option(None, envvar="PUNCTUAL_LEASE_TOKEN"),
):
    ctx.obj.request(
        "DELETE",
        f"/{ctx.obj.task_id(task_id)}",
        json={"revision": revision, "lease_token": lease_token},
    )


@app.command()
def claim(
    ctx: typer.Context,
    task_id: str,
    owner: str,
    seconds: int = 900,
    lease_token: str | None = typer.Option(None, envvar="PUNCTUAL_LEASE_TOKEN"),
):
    """Claim work; supply a pre-saved random token to make retries recoverable."""
    ctx.obj.request(
        "POST",
        f"/{ctx.obj.task_id(task_id)}/claim",
        json={"owner": owner, "seconds": seconds, "lease_token": lease_token},
    )


@app.command()
def force_release(
    ctx: typer.Context,
    task_id: str,
    revision: Annotated[int, typer.Option()],
    lease_id: Annotated[str, typer.Option()],
    reason: Annotated[str, typer.Option()],
):
    """Override a lease without its token, checking revision and public lease ID."""
    ctx.obj.request(
        "POST",
        f"/{ctx.obj.task_id(task_id)}/force-release",
        json={
            "revision": revision,
            "lease_id": lease_id,
            "reason": reason,
        },
    )


@app.command()
def lease_history(ctx: typer.Context, task_id: str):
    """Read durable forced-release records, including for deleted tasks."""
    ctx.obj.request("GET", f"/{ctx.obj.task_id(task_id)}/lease-history")


@app.command()
def renew(
    ctx: typer.Context,
    task_id: str,
    lease_token: str = typer.Option(..., envvar="PUNCTUAL_LEASE_TOKEN"),
    seconds: int = 900,
):
    ctx.obj.request(
        "POST",
        f"/{ctx.obj.task_id(task_id)}/renew",
        json={"lease_token": lease_token, "seconds": seconds},
    )


@app.command()
def release(
    ctx: typer.Context,
    task_id: str,
    lease_token: str = typer.Option(..., envvar="PUNCTUAL_LEASE_TOKEN"),
):
    ctx.obj.request(
        "POST",
        f"/{ctx.obj.task_id(task_id)}/release",
        json={"lease_token": lease_token},
    )
