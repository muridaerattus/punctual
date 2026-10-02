"""Data-only contracts for bounded read workflows (no lease credentials)."""

from typing import TypedDict

from .schemas import Status


class BoardSummary(TypedDict):
    id: int
    name: str
    prefix: str


class CompactTask(TypedDict):
    id: int
    key: str
    board_id: int
    title: str
    status: Status
    assignee: str | None
    parent_id: int | None
    parent_key: str | None
    revision: int
    created_at: float
    updated_at: float
    lease_owner: str | None
    lease_expires_at: float | None
    lease_id: str | None


class FullTask(CompactTask):
    number: int
    description: str


class TaskCounts(TypedDict):
    total: int
    by_status: dict[Status, int]
    claimed: int
    unclaimed: int
    available: int


class BoardCounts(TaskCounts):
    top_level: TaskCounts
    subtasks: TaskCounts


class TaskPage(TypedDict):
    board: BoardSummary
    items: list[CompactTask]
    next_cursor: int | None
    truncated: bool
    as_of: float


class TaskContext(TypedDict):
    board: BoardSummary
    task: FullTask
    parent: FullTask | None
    subtasks: list[CompactTask]
    child_counts: TaskCounts
    next_cursor: int | None
    truncated: bool
    as_of: float


class BoardOverview(TypedDict):
    board: BoardSummary
    counts: BoardCounts
    samples: list[CompactTask]
    truncated: bool
    as_of: float


class LeaseHistoryItem(TypedDict):
    id: int
    task_id: int
    revision: int
    lease_id: str
    lease_owner: str
    released_at: float
    reason: str


class LeaseHistoryPage(TypedDict):
    items: list[LeaseHistoryItem]
    next_cursor: int | None
    truncated: bool
