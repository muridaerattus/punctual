"""Bounded, read-only workflows shared by service adapters."""

import time

from sqlalchemy import String, case, func, or_, select
from sqlalchemy.orm import Session, aliased

from ..db.models import Board, LeaseRelease, Task
from .errors import Conflict
from .read_schemas import (
    BoardOverview,
    BoardSummary,
    LeaseHistoryPage,
    TaskContext,
    TaskCounts,
    TaskPage,
)
from .references import MAX_ID, resolve_task, task_condition

STATUSES = ("To Do", "In Progress", "Complete")


class AmbiguousBoard(Conflict):
    def __init__(self, candidates: list[BoardSummary], truncated: bool = False):
        super().__init__("ambiguous_board", "Board name is ambiguous; use a prefix")
        self.details = {"candidates": candidates, "truncated": truncated}


def board_summary(board: Board) -> BoardSummary:
    return {"id": board.id, "name": board.name, "prefix": board.prefix}


def resolve_board(session: Session, board: str) -> Board:
    """Prefer an exact prefix, then an exact name; never choose a default board."""
    if not isinstance(board, str) or not board.strip():
        raise Conflict("invalid_board", "A board prefix or exact name is required", 422)
    match = session.scalar(select(Board).where(Board.prefix == board).limit(1))
    if match is not None:
        return match
    # Probe with a bound; ambiguity responses contain only bounded public metadata.
    matches = session.scalars(
        select(Board).where(Board.name == board).order_by(Board.id).limit(2)
    ).all()
    if not matches:
        raise Conflict("not_found", "Board not found", 404)
    if len(matches) > 1:
        candidates = [
            dict(row)
            for row in session.execute(
                select(Board.id, Board.name, Board.prefix)
                .where(Board.name == board)
                .order_by(Board.id)
                .limit(101)
            ).mappings()
        ]
        raise AmbiguousBoard(candidates[:100], truncated=len(candidates) > 100)
    return matches[0]


def validate_page(limit: int, cursor: int | None = None):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise Conflict("invalid_limit", "Limit must be an integer from 1 to 100", 422)
    if cursor is not None and (type(cursor) is not int or not 1 <= cursor <= MAX_ID):
        raise Conflict("invalid_cursor", "Cursor must be a positive row ID", 422)


def _claimed(as_of: float):
    return func.coalesce(Task.lease_expires_at, 0) > as_of


def _projection(as_of: float, *, full=False):
    """Explicit columns keep descriptions and credentials out of list queries."""
    parent = aliased(Task)
    claimed = _claimed(as_of)
    columns = [
        Task.id,
        (Board.prefix + "-" + Task.number.cast(String)).label("key"),
        Task.board_id,
        Task.title,
        Task.status,
        Task.assignee,
        Task.parent_id,
        (Board.prefix + "-" + parent.number.cast(String)).label("parent_key"),
        Task.revision,
        Task.created_at,
        Task.updated_at,
        case((claimed, Task.lease_owner), else_=None).label("lease_owner"),
        case((claimed, Task.lease_expires_at), else_=None).label("lease_expires_at"),
        case((claimed, Task.lease_id), else_=None).label("lease_id"),
    ]
    if full:
        columns.extend([Task.number, Task.description])
    return (
        select(*columns)
        .join(Board, Board.id == Task.board_id)
        .outerjoin(parent, parent.id == Task.parent_id)
    )


def _page(session: Session, statement, limit: int, cursor: int | None):
    if cursor is not None:
        statement = statement.where(Task.id > cursor)
    rows = session.execute(statement.order_by(Task.id).limit(limit + 1)).mappings()
    items = [dict(row) for row in rows]
    truncated = len(items) > limit
    items = items[:limit]
    return {
        "items": items,
        "next_cursor": items[-1]["id"] if truncated else None,
        "truncated": truncated,
    }


def _empty_counts() -> TaskCounts:
    return {
        "total": 0,
        "by_status": dict.fromkeys(STATUSES, 0),
        "claimed": 0,
        "unclaimed": 0,
        "available": 0,
    }


def _counts(session: Session, condition, as_of: float):
    """At most twelve aggregate rows, regardless of the number of tasks."""
    child = Task.parent_id.is_not(None)
    claimed = _claimed(as_of)
    rows = session.execute(
        select(child, Task.status, claimed, func.count())
        .where(condition)
        .group_by(child, Task.status, claimed)
    )
    counts = _empty_counts()
    counts.update(top_level=_empty_counts(), subtasks=_empty_counts())
    for is_child, status, is_claimed, total in rows:
        for bucket in (counts, counts["subtasks" if is_child else "top_level"]):
            bucket["total"] += total
            bucket["by_status"][status] += total
            bucket["claimed" if is_claimed else "unclaimed"] += total
            if status == "To Do" and not is_claimed:
                bucket["available"] += total
    return counts


class ReadWorkflows:
    """Mixin for TaskService; each workflow uses one read transaction."""

    def query_tasks(
        self,
        board: str,
        status=None,
        assignee=None,
        query=None,
        parent_id=None,
        available: bool | None = None,
        limit=50,
        cursor: int | None = None,
    ) -> TaskPage:
        """ID-ordered compact tasks; available filters active claims, not status."""
        validate_page(limit, cursor)
        if status is not None and status not in STATUSES:
            raise Conflict("invalid_status", "Unknown task status", 422)
        if available is not None and type(available) is not bool:
            raise Conflict("invalid_available", "Available must be a boolean", 422)
        if parent_id is not None and (
            type(parent_id) is not int or not 1 <= parent_id <= MAX_ID
        ):
            raise Conflict("invalid_parent", "Parent must be a positive row ID", 422)
        as_of = time.time()
        with self.database.session() as session:
            resolved = resolve_board(session, board)
            statement = _projection(as_of).where(Task.board_id == resolved.id)
            if status is not None:
                statement = statement.where(Task.status == status)
            if assignee is not None:
                statement = statement.where(Task.assignee == assignee)
            if parent_id is not None:
                statement = statement.where(Task.parent_id == parent_id)
            if available is not None:
                statement = statement.where(
                    ~_claimed(as_of) if available else _claimed(as_of)
                )
            if query:
                statement = statement.where(
                    or_(
                        func.instr(func.lower(Task.title), func.lower(query)) > 0,
                        func.instr(func.lower(Task.description), func.lower(query)) > 0,
                        func.lower(Board.prefix + "-" + Task.number.cast(String))
                        == query.lower(),
                    )
                )
            return {
                "board": board_summary(resolved),
                **_page(session, statement, limit, cursor),
                "as_of": as_of,
            }

    def get_task_context(self, key: int | str, limit=50, cursor=None) -> TaskContext:
        validate_page(limit, cursor)
        condition = task_condition(key)
        as_of = time.time()
        with self.database.session() as session:
            task = (
                session.execute(_projection(as_of, full=True).where(condition).limit(1))
                .mappings()
                .first()
            )
            if task is None:
                raise Conflict("not_found", "Task not found", 404)
            parent = None
            if task["parent_id"] is not None:
                parent = (
                    session.execute(
                        _projection(as_of, full=True)
                        .where(Task.id == task["parent_id"])
                        .limit(1)
                    )
                    .mappings()
                    .first()
                )
            condition = Task.parent_id == task["id"]
            children = _page(
                session, _projection(as_of).where(condition), limit, cursor
            )
            counts = _counts(session, condition, as_of)
            return {
                "board": board_summary(session.get(Board, task["board_id"])),
                "task": dict(task),
                "parent": dict(parent) if parent is not None else None,
                "subtasks": children["items"],
                "child_counts": {
                    k: v
                    for k, v in counts.items()
                    if k not in ("top_level", "subtasks")
                },
                "next_cursor": children["next_cursor"],
                "truncated": children["truncated"],
                "as_of": as_of,
            }

    def board_overview(self, board: str, limit=10) -> BoardOverview:
        """Exact counts and an ID-ordered sample bounded across the entire board."""
        validate_page(limit)
        as_of = time.time()
        with self.database.session() as session:
            resolved = resolve_board(session, board)
            condition = Task.board_id == resolved.id
            page = _page(session, _projection(as_of).where(condition), limit, None)
            return {
                "board": board_summary(resolved),
                "counts": _counts(session, condition, as_of),
                "samples": page["items"],
                "truncated": page["truncated"],
                "as_of": as_of,
            }

    def find_available_work(
        self, board: str, assignee=None, query=None, limit=50, cursor=None
    ) -> TaskPage:
        return self.query_tasks(
            board,
            status="To Do",
            assignee=assignee,
            query=query,
            available=True,
            limit=limit,
            cursor=cursor,
        )

    def get_lease_history(
        self, task_id: int | str, limit=50, cursor=None
    ) -> LeaseHistoryPage:
        """Read durable forced-release events, even after a task is deleted."""
        validate_page(limit, cursor)
        with self.database.session() as session:
            if isinstance(task_id, str):
                task_id = resolve_task(session, task_id).id
            if type(task_id) is not int or not 1 <= task_id <= MAX_ID:
                raise Conflict("invalid_task", "Task must be a positive row ID", 422)
            statement = select(*LeaseRelease.__table__.columns).where(
                LeaseRelease.task_id == task_id
            )
            if cursor is not None:
                statement = statement.where(LeaseRelease.id > cursor)
            rows = session.execute(
                statement.order_by(LeaseRelease.id).limit(limit + 1)
            ).mappings()
            items = [dict(row) for row in rows]
            truncated = len(items) > limit
            items = items[:limit]
            return {
                "items": items,
                "next_cursor": items[-1]["id"] if truncated else None,
                "truncated": truncated,
            }
