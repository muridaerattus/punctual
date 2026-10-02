"""Public MCP contracts, including token-free read projections."""

from typing import Annotated

from pydantic import BaseModel, Field, JsonValue

from ..tasks.schemas import Status, TaskPatch

PositiveId = Annotated[int, Field(gt=0, le=9223372036854775807)]
Limit = Annotated[int, Field(ge=1, le=100)]
Seconds = Annotated[int, Field(ge=30, le=86400)]
Owner = Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")]
Token = Annotated[
    str, Field(min_length=32, max_length=100, pattern=r"^[A-Za-z0-9_-]{32,100}$")
]
ExistingToken = Annotated[
    str,
    Field(
        min_length=1, description="Owned lease token, including migrated legacy tokens"
    ),
]
BoardSelector = Annotated[str, Field(min_length=1, pattern=r"\S")]
TicketKey = Annotated[str, Field(pattern=r"^[A-Z]{1,8}-[1-9][0-9]*$")]


class MCPTaskPatch(TaskPatch):
    lease_token: ExistingToken | None = None


class Board(BaseModel):
    id: PositiveId
    name: str
    prefix: str


class TaskSummary(BaseModel):
    id: PositiveId
    board_id: PositiveId
    key: str
    title: str
    status: Status
    assignee: str | None
    parent_id: PositiveId | None
    parent_key: str | None
    revision: PositiveId
    lease_owner: str | None
    lease_expires_at: float | None
    lease_id: str | None
    created_at: float
    updated_at: float


class Task(TaskSummary):
    number: PositiveId
    description: str


class ClaimedTask(Task):
    lease_token: str | None = None


class Deleted(BaseModel):
    deleted: PositiveId


class TaskPage(BaseModel):
    board: Board
    items: list[TaskSummary]
    next_cursor: PositiveId | None
    truncated: bool
    as_of: float


class TaskCounts(BaseModel):
    total: int
    by_status: dict[Status, int]
    claimed: int
    unclaimed: int
    available: int


class BoardCounts(TaskCounts):
    top_level: TaskCounts
    subtasks: TaskCounts


class TaskContext(BaseModel):
    board: Board
    task: Task
    parent: Task | None
    subtasks: list[TaskSummary]
    child_counts: TaskCounts
    next_cursor: PositiveId | None
    truncated: bool
    as_of: float


class BoardOverview(BaseModel):
    board: Board
    counts: BoardCounts
    samples: list[TaskSummary]
    truncated: bool
    as_of: float


class LeaseEvent(BaseModel):
    id: PositiveId
    task_id: PositiveId
    revision: PositiveId
    lease_id: str
    lease_owner: str
    released_at: float
    reason: str


class LeaseHistory(BaseModel):
    items: list[LeaseEvent]
    next_cursor: PositiveId | None
    truncated: bool


class TaskWorkflow(BaseModel):
    task: Task
    replayed: bool


class TaskTree(BaseModel):
    parent: Task
    children: list[Task]
    replayed: bool


class Error(BaseModel):
    code: str
    message: str
    details: JsonValue | None = None


class Envelope[Payload](BaseModel):
    ok: bool
    data: Payload | None = None
    error: Error | None = None
    summary: str | None = None
