from fastmcp import FastMCP

from ..tasks.references import TaskReference
from ..tasks.schemas import BoardInput, ForceReleaseInput, Status, TaskInput
from ..tasks.service import TaskService
from ..tasks.write_schemas import CompleteTaskInput, StartTaskInput, TaskTreeInput
from .helpers import ErrorEnvelopeMiddleware, result
from .schemas import (
    Board,
    BoardOverview,
    BoardSelector,
    ClaimedTask,
    Deleted,
    Envelope,
    ExistingToken,
    LeaseHistory,
    Limit,
    MCPTaskPatch,
    Owner,
    PositiveId,
    Seconds,
    Task,
    TaskContext,
    TaskPage,
    TaskTree,
    TaskWorkflow,
    TicketKey,
    Token,
)


def create_mcp(store: TaskService, auth=None):
    mcp = FastMCP(
        "Punctual",
        auth=auth,
        instructions=(
            "List boards and select an exact prefix or name. Prefer query_tasks or "
            "find_available_work, then get_task_context by stable ticket key or numeric ID. Never "
            "claim by title. Prefer start_task and complete_task for atomic workflows. "
            "Save random request IDs and URL-safe lease tokens before calling writes; "
            "retry with the identical request ID and payload after a lost response. "
            "Use the observed revision; never automatically refresh revisions to retry "
            "a conflict. Claim owner identifies the lease holder, independently of assignee. "
            "Renew long-running leases and release when done. Granular mutations accept "
            "an exact ticket key or numeric ID in task_id; no lookup call is needed. "
            "Retry claim_task with the same owner/token to recover its response. "
            "If a token is lost, fetch current metadata and explicitly force_release_lease "
            "using its revision, lease_id and a reason."
        ),
    )
    mcp.add_middleware(ErrorEnvelopeMiddleware())

    def tool(payload, *, read=False, destructive=False, idempotent=False):
        return mcp.tool(
            output_schema=Envelope[payload].model_json_schema(),
            annotations={
                "readOnlyHint": read,
                "destructiveHint": destructive,
                "idempotentHint": read or idempotent,
                "openWorldHint": False,
            },
        )

    @tool(list[Board], read=True)
    def list_boards():
        """List boards and their immutable ticket prefixes."""
        return result(list[Board], store.list_boards)

    @tool(Board)
    def create_board(board: BoardInput):
        """Create a board with a unique prefix of 1–8 uppercase ASCII letters."""
        return result(Board, store.create_board, board)

    @tool(TaskPage, read=True)
    def query_tasks(
        board: BoardSelector,
        status: Status | None = None,
        assignee: str | None = None,
        query: str | None = None,
        parent_id: PositiveId | None = None,
        available: bool | None = None,
        limit: Limit = 50,
        cursor: PositiveId | None = None,
    ):
        """Query compact tasks using an exact board prefix or name and a bounded page."""
        return result(
            TaskPage,
            store.query_tasks,
            board,
            status=status,
            assignee=assignee,
            query=query,
            parent_id=parent_id,
            available=available,
            limit=limit,
            cursor=cursor,
            summary=lambda d: (
                f"Showing {len(d['items'])} tasks"
                + ("; more available." if d["truncated"] else ".")
            ),
        )

    @tool(TaskContext, read=True)
    def get_task_context(
        key: TaskReference, limit: Limit = 50, cursor: PositiveId | None = None
    ):
        """Get full task/parent detail and paged subtasks by exact ticket key or numeric ID."""
        return result(
            TaskContext,
            store.get_task_context,
            key,
            limit=limit,
            cursor=cursor,
            summary=lambda d: (
                f"Context for {d['task']['key']}; showing {len(d['subtasks'])} of "
                f"{d['child_counts']['total']} subtasks."
            ),
        )

    @tool(BoardOverview, read=True)
    def board_overview(board: BoardSelector, limit: Limit = 10):
        """Get board counts and bounded task samples using an exact prefix or name."""
        return result(
            BoardOverview,
            store.board_overview,
            board,
            limit=limit,
            summary=lambda d: (
                f"{d['board']['prefix']}: {d['counts']['top_level']['total']} top-level "
                f"tasks, {d['counts']['subtasks']['total']} subtasks; "
                f"{d['counts']['claimed']} claimed."
            ),
        )

    @tool(TaskPage, read=True)
    def find_available_work(
        board: BoardSelector,
        assignee: str | None = None,
        query: str | None = None,
        limit: Limit = 50,
        cursor: PositiveId | None = None,
    ):
        """Find a bounded page of unclaimed To Do tasks in an exact board."""
        return result(
            TaskPage,
            store.find_available_work,
            board,
            assignee=assignee,
            query=query,
            limit=limit,
            cursor=cursor,
            summary=lambda d: (
                f"Showing {len(d['items'])} unclaimed To Do tasks"
                + ("; more available." if d["truncated"] else ".")
            ),
        )

    @tool(LeaseHistory, read=True)
    def get_lease_history(
        task_id: TaskReference, limit: Limit = 50, cursor: PositiveId | None = None
    ):
        """Get forced-release history by key or ID; use a numeric ID after deletion."""
        return result(
            LeaseHistory,
            store.get_lease_history,
            task_id,
            limit=limit,
            cursor=cursor,
            summary=lambda d: (
                f"Showing {len(d['items'])} forced-release records"
                + ("; more available." if d["truncated"] else ".")
            ),
        )

    @tool(Task)
    def create_task(task: TaskInput):
        """Create a task or a one-level subtask."""
        return result(Task, store.create, task)

    @tool(Task, destructive=True)
    def update_task(task_id: TaskReference, changes: MCPTaskPatch):
        """Edit by key or ID using an expected revision; active leases require their token."""
        return result(Task, store.update, task_id, changes)

    @tool(Deleted, destructive=True)
    def delete_task(
        task_id: TaskReference,
        revision: PositiveId,
        lease_token: ExistingToken | None = None,
    ):
        """Delete by key or ID, respecting subtasks, revisions and leases."""
        return result(Deleted, store.delete, task_id, revision, lease_token)

    @tool(ClaimedTask)
    def claim_task(
        task_id: TaskReference,
        owner: Owner,
        seconds: Seconds = 900,
        lease_token: Token | None = None,
    ):
        """Claim by key or ID; save a random token first. Owner is independent of assignee.

        Retry with the same owner/token to recover an active claim without renewing it.
        If omitted, save the server-generated token from the response.
        """
        return result(
            ClaimedTask,
            store.lease,
            task_id,
            "claim",
            owner=owner,
            seconds=seconds,
            token=lease_token,
        )

    @tool(ClaimedTask)
    def renew_lease(
        task_id: TaskReference, lease_token: ExistingToken, seconds: Seconds = 900
    ):
        """Extend your active task lease by exact key or numeric ID."""
        return result(
            ClaimedTask,
            store.lease,
            task_id,
            "renew",
            token=lease_token,
            seconds=seconds,
        )

    @tool(Task, destructive=True)
    def release_lease(task_id: TaskReference, lease_token: ExistingToken):
        """Release your active task lease by exact key or numeric ID."""
        return result(Task, store.lease, task_id, "release", token=lease_token)

    @tool(Task, destructive=True)
    def force_release_lease(task_id: TaskReference, release: ForceReleaseInput):
        """Override by key or ID using the current revision, lease ID and reason."""
        return result(Task, store.force_release, task_id, release)

    @tool(TaskWorkflow, destructive=True, idempotent=True)
    def start_task(key: TicketKey, data: StartTaskInput):
        """Atomically claim and start a ticket; save request ID/token before calling."""
        return result(
            TaskWorkflow,
            store.start_task,
            key,
            data,
            summary=lambda d: (
                f"Started {d['task']['key']} (replayed={str(d['replayed']).lower()})."
            ),
        )

    @tool(TaskWorkflow, destructive=True, idempotent=True)
    def complete_task(key: TicketKey, data: CompleteTaskInput):
        """Atomically complete and release a ticket with a saved request ID."""
        return result(
            TaskWorkflow,
            store.complete_task,
            key,
            data,
            summary=lambda d: (
                f"Completed {d['task']['key']} (replayed={str(d['replayed']).lower()})."
            ),
        )

    @tool(TaskTree, idempotent=True)
    def create_task_tree(data: TaskTreeInput):
        """Atomically create a parent and up to 50 children with a saved request ID."""
        return result(
            TaskTree,
            store.create_task_tree,
            data,
            summary=lambda d: (
                f"Created {d['parent']['key']} with {len(d['children'])} children (replayed={str(d['replayed']).lower()})."
            ),
        )

    return mcp
