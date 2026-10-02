import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from pydantic import ValidationError
from sqlalchemy import event, select

from punctual.db.idempotency_models import IdempotencyReceipt
from punctual.db.models import Board, Task
from punctual.tasks.errors import Conflict
from punctual.tasks.schemas import BoardInput, TaskInput, TaskPatch
from punctual.tasks.service import TaskService
from punctual.tasks.write_schemas import (
    CompleteTaskInput,
    StartTaskInput,
    TaskTreeInput,
)


@pytest.fixture
def workflow(tmp_path):
    service = TaskService(str(tmp_path / "workflows.db"))
    yield service
    service.database.engine.dispose()


def start_input(**changes):
    return StartTaskInput(
        **{
            "revision": 1,
            "owner": "worker",
            "lease_token": secrets.token_urlsafe(32),
            "request_id": secrets.token_urlsafe(32),
            **changes,
        }
    )


def tree_input(**changes):
    return TaskTreeInput(
        **{
            "board": "PUN",
            "parent": {"title": "Parent", "status": "Complete"},
            "children": [{"title": "Child"}, {"title": "Other"}],
            "request_id": secrets.token_urlsafe(32),
            **changes,
        }
    )


def test_start_complete_restart_and_deleted_replay(workflow):
    task = workflow.create(TaskInput(title="Work", assignee="original"))
    child = workflow.create(TaskInput(title="Child", parent_id=task["id"]))
    data = start_input()
    started = workflow.start_task(task["key"], data)
    assert started["replayed"] is False
    assert started["task"]["status"] == "In Progress"
    assert started["task"]["revision"] == 2
    assert started["task"]["assignee"] == "original"
    assert started["task"]["lease_owner"] == "worker"
    assert started["task"]["lease_expires_at"] is not None
    assert "lease_token" not in started["task"]
    workflow.database.engine.dispose()
    restarted = TaskService(workflow.path)
    try:
        assert restarted.start_task(task["key"], data) == {
            **started,
            "replayed": True,
        }
        complete = CompleteTaskInput(
            revision=2,
            lease_token=data.lease_token,
            request_id=secrets.token_urlsafe(32),
        )
        completed = restarted.complete_task(task["key"], complete)
        assert completed["task"]["status"] == "Complete"
        assert completed["task"]["revision"] == 3
        assert completed["task"]["lease_id"] is None
        assert restarted.get(child["id"])["status"] == "To Do"
        restarted.delete(child["id"], 1)
        restarted.delete(task["id"], 3)
        assert restarted.complete_task(task["key"], complete) == {
            **completed,
            "replayed": True,
        }
        assert restarted.start_task(task["key"], data) == {
            **started,
            "replayed": True,
        }
        with restarted.database.session() as session:
            receipts = list(session.scalars(select(IdempotencyReceipt)))
            assert len(receipts) == 2
            assert all(data.lease_token not in r.outcome for r in receipts)
            assert all(
                "lease_token" not in json.loads(r.outcome)["task"] for r in receipts
            )
    finally:
        restarted.database.engine.dispose()


def test_replay_does_not_restore_reclaimed_lease_or_old_edit(workflow):
    task = workflow.create(TaskInput(title="Work"))
    data = start_input(assignee="new")
    original = workflow.start_task(task["key"], data)
    workflow.update(
        task["id"], TaskPatch(revision=2, lease_token=data.lease_token, title="Edited")
    )
    workflow.lease(task["id"], "release", token=data.lease_token)
    reclaimed = workflow.lease(task["id"], "claim", owner="someone else")
    assert workflow.start_task(task["key"], data) == {**original, "replayed": True}
    current = workflow.get(task["id"])
    assert current["title"] == "Edited"
    assert current["lease_id"] == reclaimed["lease_id"]
    assert current["assignee"] == "new"


@pytest.mark.parametrize(
    "change",
    [
        {"revision": 2},
        {"owner": "other"},
        {"assignee": None},
        {"seconds": 30},
        {"lease_token": "x" * 32},
    ],
)
def test_changed_start_request_rejected(workflow, change):
    task = workflow.create(TaskInput(title="Work"))
    data = start_input()
    workflow.start_task(task["key"], data)
    with pytest.raises(Conflict, match="Request ID"):
        workflow.start_task(task["key"], data.model_copy(update=change))
    assert workflow.get(task["id"])["revision"] == 2


def test_cross_operation_request_reuse_rejected(workflow):
    task = workflow.create(TaskInput(title="Work"))
    data = start_input()
    workflow.start_task(task["key"], data)
    with pytest.raises(Conflict) as error:
        workflow.complete_task(
            task["key"],
            CompleteTaskInput(
                revision=2, lease_token=data.lease_token, request_id=data.request_id
            ),
        )
    assert error.value.code == "request_conflict"


@pytest.mark.parametrize("case", ["stale", "locked", "complete"])
def test_start_failure_rolls_back(workflow, case):
    task = workflow.create(
        TaskInput(title="Work", status="Complete" if case == "complete" else "To Do")
    )
    if case == "locked":
        workflow.lease(task["id"], "claim", owner="other")
    before = workflow.get(task["id"])
    with pytest.raises(Conflict):
        workflow.start_task(
            task["key"], start_input(revision=2 if case == "stale" else 1)
        )
    assert workflow.get(task["id"]) == before
    with workflow.database.session() as session:
        assert session.scalar(select(IdempotencyReceipt)) is None


@pytest.mark.parametrize("case", ["unclaimed", "expired", "wrong_token", "stale"])
def test_complete_requires_active_owned_lease_and_revision(workflow, case):
    task = workflow.create(TaskInput(title="Work"))
    data = start_input()
    revision = 1
    if case != "unclaimed":
        workflow.start_task(task["key"], data)
        revision = 2
    if case == "expired":
        with workflow.database.session(write=True) as session:
            session.get(Task, task["id"]).lease_expires_at = 1
    before = workflow.get(task["id"])
    with pytest.raises(Conflict):
        workflow.complete_task(
            task["key"],
            CompleteTaskInput(
                revision=1 if case == "stale" else revision,
                lease_token="z" * 32 if case == "wrong_token" else data.lease_token,
                request_id=secrets.token_urlsafe(32),
            ),
        )
    assert workflow.get(task["id"]) == before


def test_matching_existing_claim_preserves_expiry_and_clears_assignment(workflow):
    task = workflow.create(TaskInput(title="Work", assignee="old"))
    data = start_input(assignee=None)
    claimed = workflow.lease(
        task["id"], "claim", owner=data.owner, token=data.lease_token
    )
    started = workflow.start_task(task["key"], data)["task"]
    assert started["lease_expires_at"] == claimed["lease_expires_at"]
    assert started["lease_id"] == claimed["lease_id"]
    assert started["assignee"] is None


def test_receipt_failure_rolls_back_task_and_lease(workflow):
    task = workflow.create(TaskInput(title="Work"))

    def fail(*args):
        raise RuntimeError("receipt failure")

    event.listen(IdempotencyReceipt, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="receipt failure"):
            workflow.start_task(task["key"], start_input())
    finally:
        event.remove(IdempotencyReceipt, "before_insert", fail)
    assert workflow.get(task["id"]) == task


@pytest.mark.parametrize("identical", [False, True])
def test_concurrent_starts(workflow, identical):
    task = workflow.create(TaskInput(title="Work"))
    data = start_input()
    barrier = Barrier(2)

    def run(request):
        barrier.wait()
        try:
            return workflow.start_task(task["key"], request)
        except Conflict as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        futures = [
            pool.submit(run, data),
            pool.submit(run, data if identical else start_input()),
        ]
        results = [f.result() for f in futures]
    if identical:
        assert sorted(r["replayed"] for r in results) == [False, True]
    else:
        assert sum(isinstance(r, dict) for r in results) == 1
        assert "task_locked" in results
    assert workflow.get(task["id"])["revision"] == 2


def test_tree_numbering_restart_deleted_replay_and_conflict(workflow):
    board = workflow.create_board(BoardInput(name="Example", prefix="EX"))
    data = tree_input(board="Example")
    result = workflow.create_task_tree(data)
    assert result["parent"]["key"] == "EX-1"
    assert [c["key"] for c in result["children"]] == ["EX-2", "EX-3"]
    assert all(c["parent_key"] == "EX-1" for c in result["children"])
    assert all(c["status"] == "To Do" for c in result["children"])
    for child in result["children"]:
        workflow.delete(child["id"], 1)
    workflow.delete(result["parent"]["id"], 1)
    workflow.database.engine.dispose()
    restarted = TaskService(workflow.path)
    try:
        assert restarted.create_task_tree(data) == {**result, "replayed": True}
        next_task = restarted.create(TaskInput(title="Next", board_id=board["id"]))
        assert next_task["key"] == "EX-4"
        with pytest.raises(Conflict) as error:
            restarted.create_task_tree(data.model_copy(update={"board": "PUN"}))
        assert error.value.code == "request_conflict"
    finally:
        restarted.database.engine.dispose()


def test_tree_failure_rolls_back_parent_children_sequence_and_receipt(workflow):
    def fail(mapper, connection, target):
        if target.title == "Other":
            raise RuntimeError("child failure")

    event.listen(Task, "before_insert", fail)
    data = tree_input()
    try:
        with pytest.raises(RuntimeError, match="child failure"):
            workflow.create_task_tree(data)
    finally:
        event.remove(Task, "before_insert", fail)
    with workflow.database.session() as session:
        assert session.scalar(select(Task)) is None
        assert session.scalar(select(IdempotencyReceipt)) is None
        assert session.get(Board, 1).next_number == 1
    assert workflow.create_task_tree(data)["parent"]["key"] == "PUN-1"


@pytest.mark.parametrize(
    "changes",
    [
        {"children": [{"title": " "}]},
        {"children": [{"title": "x"}] * 51},
        {"children": [{"title": "x", "parent_id": 1}]},
        {"parent": {"title": "x", "board_id": 2}},
        {"request_id": "short"},
    ],
)
def test_tree_schema_rejects_invalid_whole_request(changes):
    with pytest.raises(ValidationError):
        tree_input(**changes)


def test_tree_race_replays_without_duplicates(workflow):
    data = tree_input()
    barrier = Barrier(2)

    def run():
        barrier.wait()
        return workflow.create_task_tree(data)

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        results = [f.result() for f in futures]
    assert sorted(r["replayed"] for r in results) == [False, True]
    assert len(workflow.list()) == 3


def test_complete_receipt_failure_restores_status_and_owned_lease(workflow):
    task = workflow.create(TaskInput(title="Work"))
    data = start_input()
    started = workflow.start_task(task["key"], data)["task"]
    complete = CompleteTaskInput(
        revision=2, lease_token=data.lease_token, request_id=secrets.token_urlsafe(32)
    )

    def fail(*args):
        raise RuntimeError("receipt failure")

    event.listen(IdempotencyReceipt, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="receipt failure"):
            workflow.complete_task(task["key"], complete)
    finally:
        event.remove(IdempotencyReceipt, "before_insert", fail)
    assert workflow.get(task["id"]) == started
    assert workflow.complete_task(task["key"], complete)["replayed"] is False


@pytest.mark.parametrize("identical", [False, True])
def test_concurrent_completions(workflow, identical):
    task = workflow.create(TaskInput(title="Work"))
    data = start_input()
    workflow.start_task(task["key"], data)
    complete = CompleteTaskInput(
        revision=2, lease_token=data.lease_token, request_id=secrets.token_urlsafe(32)
    )
    other = (
        complete
        if identical
        else complete.model_copy(update={"request_id": secrets.token_urlsafe(32)})
    )
    barrier = Barrier(2)

    def run(request):
        barrier.wait()
        try:
            return workflow.complete_task(task["key"], request)
        except Conflict as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(run, request) for request in (complete, other)]
        results = [f.result() for f in futures]
    if identical:
        assert sorted(r["replayed"] for r in results) == [False, True]
    else:
        assert sum(isinstance(r, dict) for r in results) == 1
        assert "revision_conflict" in results
    assert workflow.get(task["id"])["revision"] == 3


@pytest.mark.parametrize("board", ["missing", "Duplicate"])
def test_tree_board_resolution_failures_do_not_write(workflow, board):
    workflow.create_board(BoardInput(name="Duplicate", prefix="A"))
    workflow.create_board(BoardInput(name="Duplicate", prefix="B"))
    with pytest.raises(Conflict) as error:
        workflow.create_task_tree(tree_input(board=board))
    assert error.value.code == (
        "not_found" if board == "missing" else "ambiguous_board"
    )
    with workflow.database.session() as session:
        assert session.scalar(select(IdempotencyReceipt)) is None
        assert session.scalar(select(Task)) is None
        assert all(b.next_number == 1 for b in session.scalars(select(Board)))


@pytest.mark.parametrize(
    "changes",
    [
        {"owner": " "},
        {"owner": "x" * 101},
        {"revision": 0},
        {"seconds": 29},
        {"seconds": 86401},
        {"lease_token": "x" * 31},
        {"lease_token": "x" * 101},
        {"lease_token": "!" * 32},
        {"lease_token": "é" * 32},
        {"request_id": "x" * 31},
        {"request_id": "x" * 101},
        {"request_id": "!" * 32},
    ],
)
def test_start_schema_bounds(changes):
    with pytest.raises(ValidationError):
        start_input(**changes)
