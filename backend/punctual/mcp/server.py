from fastmcp import FastMCP

from ..tasks.errors import Conflict
from ..tasks.schemas import BoardInput, ForceReleaseInput, Status, TaskInput, TaskPatch
from ..tasks.service import TaskService


def result(call, *args, **kwargs):
    try:
        return {"ok": True, "data": call(*args, **kwargs)}
    except Conflict as exc:
        return {"ok": False, "error": {"code": exc.code, "message": exc.message}}


def create_mcp(store: TaskService, auth=None):
    mcp = FastMCP(
        "Punctual",
        auth=auth,
        instructions=(
            "List boards to choose a board_id; task listing and creation default to board 1. "
            "Resolve ticket keys with get_task_by_key, then use numeric task IDs for mutations. "
            "List tasks, claim one, then update with its revision and lease token. "
            "Renew long-running leases and release when done. "
            "Prefer a random lease_token saved before claiming; retry claim with the same "
            "owner and token to recover its response. If a token is lost, fetch the task "
            "and explicitly force_release_lease using its revision, lease_id and a reason. "
            "Unclaimed tasks can be edited directly with revision checks."
        ),
    )

    @mcp.tool
    def list_boards():
        """List boards and their immutable ticket prefixes."""
        return result(store.list_boards)

    @mcp.tool
    def create_board(board: BoardInput):
        """Create a board with a unique prefix of 1–8 uppercase ASCII letters."""
        return result(store.create_board, board)

    @mcp.tool
    def get_task_by_key(key: str):
        """Resolve a stable ticket key to its numeric ID and current revision."""
        return result(store.get_by_key, key)

    @mcp.tool
    def list_tasks(
        status: Status | None = None,
        assignee: str | None = None,
        query: str | None = None,
        board_id: int = 1,
    ):
        """List tasks in a board (default 1), filtered by status, assignee or text/key."""
        return result(store.list, status, assignee, query, board_id)

    @mcp.tool
    def get_task(task_id: int):
        """Get a task's current revision and public lease metadata."""
        return result(store.get, task_id)

    @mcp.tool
    def create_task(task: TaskInput):
        """Create a task or a one-level subtask."""
        return result(store.create, task)

    @mcp.tool
    def update_task(task_id: int, changes: TaskPatch):
        """Edit using an expected revision; active leases require their token."""
        return result(store.update, task_id, changes)

    @mcp.tool
    def delete_task(task_id: int, revision: int, lease_token: str | None = None):
        """Delete a task without subtasks, respecting revisions and leases."""
        return result(store.delete, task_id, revision, lease_token)

    @mcp.tool
    def claim_task(
        task_id: int, owner: str, seconds: int = 900, lease_token: str | None = None
    ):
        """Claim work. Prefer a pre-saved random token (32–100 URL-safe characters).

        Retry with the same owner/token to recover an active claim without renewing it.
        If omitted, save the server-generated token from the response.
        """
        return result(
            store.lease,
            task_id,
            "claim",
            owner=owner,
            seconds=seconds,
            token=lease_token,
        )

    @mcp.tool
    def renew_lease(task_id: int, lease_token: str, seconds: int = 900):
        """Extend your active task lease."""
        return result(store.lease, task_id, "renew", token=lease_token, seconds=seconds)

    @mcp.tool
    def release_lease(task_id: int, lease_token: str):
        """Release your active task lease."""
        return result(store.lease, task_id, "release", token=lease_token)

    @mcp.tool
    def force_release_lease(task_id: int, release: ForceReleaseInput):
        """Explicitly override a lost/stuck lease using current revision and lease_id.

        Available to the trusted bearer-key group; records the required reason.
        Fetch current lease metadata first. A stale lease ID cannot release a new claim.
        """
        return result(store.force_release, task_id, release)

    return mcp
