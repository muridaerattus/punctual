import json

import pytest
from sqlalchemy import event, select

from punctual.db.models import LeaseRelease, Task
from punctual.tasks.errors import Conflict
from punctual.tasks.reads import AmbiguousBoard, resolve_board
from punctual.tasks.schemas import BoardInput, TaskInput
from punctual.tasks.service import TaskService


@pytest.fixture
def reads(tmp_path):
    service = TaskService(str(tmp_path / "reads.db"))
    yield service
    service.database.engine.dispose()


def create(reads, title="Task", **kwargs):
    return reads.create(TaskInput(title=title, **kwargs))


def lease_at(reads, task_id, expiry):
    with reads.database.session(write=True) as session:
        task = session.get(Task, task_id)
        task.lease_owner = "agent"
        task.lease_token = "secret-token-never-return"
        task.lease_id = "a" * 32
        task.lease_expires_at = expiry


def test_exact_resolution_duplicate_names_and_prefix_precedence(reads):
    a = reads.create_board(BoardInput(name="Shared", prefix="ONE"))
    b = reads.create_board(BoardInput(name="Shared", prefix="TWO"))
    reads.create_board(BoardInput(name="ONE", prefix="THREE"))
    assert reads.query_tasks("ONE")["board"] == a
    with pytest.raises(AmbiguousBoard) as exc:
        reads.board_overview("Shared")
    assert exc.value.code == "ambiguous_board"
    assert exc.value.details == {"candidates": [a, b], "truncated": False}
    for name in ("one", "share", " Shared "):
        with pytest.raises(Conflict, match="Board not found"):
            reads.query_tasks(name)
    with pytest.raises(Conflict) as exc:
        reads.query_tasks("")
    assert exc.value.status == 422
    with reads.database.session() as session:
        assert resolve_board(session, "Default").prefix == "PUN"
    assert reads.query_tasks("Default")["board"]["prefix"] == "PUN"


def test_query_pagination_redaction_and_sql_bounds(reads):
    tasks = [
        create(reads, f"Task {i}", description="long description") for i in range(7)
    ]
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append((statement, parameters))

    event.listen(reads.database.engine, "before_cursor_execute", capture)
    try:
        page = reads.query_tasks("PUN", limit=2)
    finally:
        event.remove(reads.database.engine, "before_cursor_execute", capture)
    queries = [(sql, args) for sql, args in statements if "FROM tasks" in sql]
    assert len(queries) == 1  # No ORM parent/board N+1 reads.
    sql, args = queries[0]
    assert "LIMIT" in sql and args[-2] == 3
    assert "description" not in sql and "lease_token" not in sql
    assert [t["id"] for t in page["items"]] == [t["id"] for t in tasks[:2]]
    assert page["next_cursor"] == tasks[1]["id"] and page["truncated"]
    all_items = page["items"][:]
    while page["next_cursor"] is not None:
        page = reads.query_tasks("PUN", limit=2, cursor=page["next_cursor"])
        all_items.extend(page["items"])
    assert [t["id"] for t in all_items] == [t["id"] for t in tasks]
    assert not page["truncated"]
    assert all("description" not in t and "lease_token" not in t for t in all_items)
    assert reads.query_tasks("PUN", cursor=tasks[-1]["id"])["items"] == []


def test_filters_and_captured_expiry(reads, monkeypatch):
    parent = create(reads, "Parent")
    expired = create(reads, "Match literal %_", parent_id=parent["id"], assignee="sam")
    active = create(reads, "Match active", assignee="sam")
    done = create(reads, "Done", status="Complete", description="hidden SEARCH")
    other = reads.create_board(BoardInput(name="Other", prefix="OTH"))
    create(reads, "Match other board", board_id=other["id"])
    lease_at(reads, expired["id"], 1000)
    lease_at(reads, active["id"], 1001)
    monkeypatch.setattr("punctual.tasks.reads.time.time", lambda: 1000)
    page = reads.query_tasks(
        "PUN", assignee="sam", query="match", parent_id=parent["id"], available=True
    )
    assert [t["id"] for t in page["items"]] == [expired["id"]]
    assert page["as_of"] == 1000
    assert all(
        page["items"][0][k] is None
        for k in ("lease_owner", "lease_id", "lease_expires_at")
    )
    claimed = reads.query_tasks("PUN", available=False)["items"]
    assert [t["id"] for t in claimed] == [active["id"]]
    assert claimed[0]["lease_owner"] == "agent"
    assert "secret-token" not in json.dumps(claimed)
    assert reads.query_tasks("PUN", query="%_")["items"][0]["id"] == expired["id"]
    assert reads.query_tasks("PUN", query="search")["items"][0]["id"] == done["id"]
    assert (
        reads.query_tasks("PUN", query=done["key"].lower())["items"][0]["id"]
        == done["id"]
    )
    assert reads.query_tasks("PUN", status="Complete")["items"][0]["id"] == done["id"]
    available = reads.find_available_work("PUN", assignee="sam", query="match", limit=1)
    assert [t["id"] for t in available["items"]] == [expired["id"]]
    assert not available["truncated"]


def test_context_full_parent_compact_children_exact_counts(reads, monkeypatch):
    parent = create(reads, "Parent", description="Full parent")
    children = [
        create(
            reads,
            f"Child {i}",
            parent_id=parent["id"],
            description="Full child",
            status=status,
        )
        for i, status in enumerate(("To Do", "Complete", "In Progress"))
    ]
    lease_at(reads, parent["id"], 1001)
    lease_at(reads, children[0]["id"], 1001)
    monkeypatch.setattr("punctual.tasks.reads.time.time", lambda: 1000)
    context = reads.get_task_context(parent["key"], limit=1)
    assert context["task"]["description"] == "Full parent"
    assert context["parent"] is None
    assert context["child_counts"] == {
        "total": 3,
        "by_status": {"To Do": 1, "In Progress": 1, "Complete": 1},
        "claimed": 1,
        "unclaimed": 2,
        "available": 0,
    }
    assert context["next_cursor"] == children[0]["id"] and context["truncated"]
    assert "description" not in context["subtasks"][0]
    following = reads.get_task_context(
        parent["key"], limit=2, cursor=context["next_cursor"]
    )
    assert [t["id"] for t in following["subtasks"]] == [t["id"] for t in children[1:]]
    assert following["child_counts"] == context["child_counts"]
    assert not following["truncated"] and following["next_cursor"] is None
    child = reads.get_task_context(children[0]["key"])
    assert child["parent"]["description"] == "Full parent"
    assert child["task"]["description"] == "Full child"
    assert child["task"]["parent_key"] == parent["key"]
    assert child["subtasks"] == [] and child["child_counts"]["total"] == 0
    assert "lease_token" not in json.dumps(child)
    assert "secret-token" not in json.dumps(child)


def test_board_overview_exact_counts_distinguish_children(reads, monkeypatch):
    parent = create(reads)
    create(reads, status="Complete")
    expired = create(reads, status="In Progress")
    child = create(reads, parent_id=parent["id"])
    create(reads, parent_id=parent["id"])
    lease_at(reads, parent["id"], 1001)
    lease_at(reads, expired["id"], 1000)
    lease_at(reads, child["id"], 1001)
    monkeypatch.setattr("punctual.tasks.reads.time.time", lambda: 1000)
    overview = reads.board_overview("PUN", limit=1)
    counts = overview["counts"]
    assert counts["total"] == 5
    assert counts["by_status"] == {"To Do": 3, "In Progress": 1, "Complete": 1}
    assert (
        counts["claimed"] == 2 and counts["unclaimed"] == 3 and counts["available"] == 1
    )
    assert counts["top_level"]["total"] == 3 and counts["top_level"]["claimed"] == 1
    assert counts["subtasks"]["total"] == 2 and counts["subtasks"]["available"] == 1
    assert len(overview["samples"]) == 1 and overview["truncated"]
    assert "description" not in overview["samples"][0]
    reads.create_board(BoardInput(name="Empty", prefix="EMPTY"))
    empty = reads.board_overview("EMPTY")
    assert empty["counts"]["total"] == 0 and not empty["truncated"]
    assert empty["samples"] == []


def test_history_retained_deleted_paginated_and_bounded(reads):
    task = create(reads)
    with reads.database.session(write=True) as session:
        for i in range(4):
            session.add(
                LeaseRelease(
                    task_id=task["id"],
                    revision=1,
                    lease_id=str(i) * 32,
                    lease_owner="agent",
                    released_at=1000 + i,
                    reason="Recovery",
                )
            )
        session.add(
            LeaseRelease(
                task_id=999,
                revision=1,
                lease_id="a" * 32,
                lease_owner="other",
                released_at=1000,
                reason="Other",
            )
        )
    reads.delete(task["id"], task["revision"])
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if "FROM lease_releases" in statement:
            statements.append((statement, parameters))

    event.listen(reads.database.engine, "before_cursor_execute", capture)
    try:
        page = reads.get_lease_history(task["id"], limit=2)
    finally:
        event.remove(reads.database.engine, "before_cursor_execute", capture)
    assert len(statements) == 1 and "LIMIT" in statements[0][0]
    assert statements[0][1][-2] == 3
    assert len(page["items"]) == 2 and page["truncated"]
    following = reads.get_lease_history(task["id"], limit=2, cursor=page["next_cursor"])
    assert len(following["items"]) == 2 and not following["truncated"]
    assert following["items"][0]["id"] > page["items"][-1]["id"]
    assert following["next_cursor"] is None
    assert all(t["task_id"] == task["id"] for t in page["items"] + following["items"])
    assert "lease_token" not in json.dumps(page)
    assert reads.get_lease_history(12345) == {
        "items": [],
        "next_cursor": None,
        "truncated": False,
    }


@pytest.mark.parametrize(
    "key,code",
    [
        ("PUN-999", "not_found"),
        ("NOPE-1", "not_found"),
        ("PUN-" + "9" * 100, "not_found"),
        ("pun-1", "invalid_key"),
        ("PUN-0", "invalid_key"),
    ],
)
def test_context_missing_or_invalid_key(reads, key, code):
    with pytest.raises(Conflict) as exc:
        reads.get_task_context(key)
    assert exc.value.code == code


@pytest.mark.parametrize("limit", [0, 101, -1, True, 1.5, "2"])
def test_limits_validated_by_all_workflows(reads, limit):
    for call in (
        lambda: reads.query_tasks("PUN", limit=limit),
        lambda: reads.get_task_context("PUN-1", limit=limit),
        lambda: reads.board_overview("PUN", limit=limit),
        lambda: reads.find_available_work("PUN", limit=limit),
        lambda: reads.get_lease_history(1, limit=limit),
    ):
        with pytest.raises(Conflict) as exc:
            call()
        assert exc.value.code == "invalid_limit"


@pytest.mark.parametrize("cursor", [0, -1, True, 1.5, "2", 2**63])
def test_cursor_validation(reads, cursor):
    with pytest.raises(Conflict) as exc:
        reads.query_tasks("PUN", cursor=cursor)
    assert exc.value.code == "invalid_cursor"


def test_read_workflows_do_not_mutate_tasks(reads):
    task = create(reads)
    lease_at(reads, task["id"], 1)
    with reads.database.session() as session:
        before = dict(session.execute(select(*Task.__table__.columns)).mappings().one())
    reads.query_tasks("PUN")
    reads.find_available_work("PUN")
    reads.get_task_context(task["key"])
    reads.board_overview("PUN")
    reads.get_lease_history(task["id"])
    with reads.database.session() as session:
        after = dict(session.execute(select(*Task.__table__.columns)).mappings().one())
    assert before == after


def test_context_and_overview_sql_limits_and_aggregate_counts(reads):
    parent = create(reads)
    for i in range(6):
        create(reads, f"Child {i}", parent_id=parent["id"])
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if "FROM tasks" in statement:
            statements.append((statement, parameters))

    event.listen(reads.database.engine, "before_cursor_execute", capture)
    try:
        reads.get_task_context(parent["key"], limit=2)
        reads.board_overview("PUN", limit=2)
    finally:
        event.remove(reads.database.engine, "before_cursor_execute", capture)
    assert len(statements) == 5  # Full task, children, two counts, board sample.
    aggregates = [sql for sql, _ in statements if "count(" in sql]
    assert len(aggregates) == 2
    assert all("GROUP BY" in sql for sql in aggregates)
    lists = [
        (sql, args)
        for sql, args in statements
        if "count(" not in sql and "tasks.description" not in sql
    ]
    assert len(lists) == 2
    assert all("LIMIT" in sql and args[-2] == 3 for sql, args in lists)
    assert all("lease_token" not in sql for sql, _ in statements)
