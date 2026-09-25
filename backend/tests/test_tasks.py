import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from punctual.db.models import Task
from punctual.tasks.errors import Conflict
from punctual.tasks.schemas import TaskInput, TaskPatch
from punctual.tasks.service import TaskService


def test_claim_race_and_restart(store):
    task = store.create(TaskInput(title="Shared work"))

    def claim(owner):
        try:
            return store.lease(task["id"], "claim", owner=owner)
        except Conflict as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(claim, [f"agent-{i}" for i in range(8)]))
    winners = [r for r in results if isinstance(r, dict)]
    assert len(winners) == 1
    assert results.count("task_locked") == 7
    restarted = TaskService(store.path)
    with pytest.raises(Conflict, match="claimed"):
        restarted.update(task["id"], TaskPatch(revision=1, title="Unauthorized"))
    changed = restarted.update(
        task["id"],
        TaskPatch(
            revision=1,
            title="Owned",
            lease_token=winners[0]["lease_token"],
        ),
    )
    assert changed["revision"] == 2
    assert "lease_token" not in changed
    assert "lease_token" not in restarted.get(task["id"])
    assert "lease_token" not in restarted.list()[0]
    restarted.database.engine.dispose()


def test_unclaimed_revision_race(store):
    task = store.create(TaskInput(title="Initial"))

    def edit(title):
        try:
            return store.update(task["id"], TaskPatch(revision=1, title=title))
        except Conflict as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, ["First", "Second"]))
    assert sum(isinstance(r, dict) for r in results) == 1
    assert "revision_conflict" in results


def test_lease_expiry_and_replacement(store):
    task = store.create(TaskInput(title="Recover me"))
    old = store.lease(task["id"], "claim", owner="old")
    renewed = store.lease(task["id"], "renew", token=old["lease_token"], seconds=3600)
    assert renewed["lease_expires_at"] > old["lease_expires_at"]
    with store.database.session(write=True) as session:
        session.get(Task, task["id"]).lease_expires_at = time.time() - 1
    assert store.get(task["id"])["lease_owner"] is None
    store.update(task["id"], TaskPatch(revision=1, title="Recovered"))
    new = store.lease(task["id"], "claim", owner="new")
    assert new["lease_token"] != old["lease_token"]
    for action in ("renew", "release"):
        with pytest.raises(Conflict, match="token"):
            store.lease(task["id"], action, token=old["lease_token"])
    with pytest.raises(Conflict, match="claimed"):
        store.delete(task["id"], 2)
    store.lease(task["id"], "release", token=new["lease_token"])
    store.delete(task["id"], 2)


def test_parent_integrity(store):
    parent = store.create(TaskInput(title="Parent"))
    child = store.create(TaskInput(title="Child", parent_id=parent["id"]))
    with pytest.raises(Conflict, match="one level"):
        store.create(TaskInput(title="Grandchild", parent_id=child["id"]))
    with pytest.raises(Conflict, match="subtasks"):
        store.delete(parent["id"], 1)
    with pytest.raises(Conflict, match="one level"):
        store.update(parent["id"], TaskPatch(revision=1, parent_id=parent["id"]))
    other = store.create(TaskInput(title="Other"))
    with pytest.raises(Conflict, match="subtasks"):
        store.update(parent["id"], TaskPatch(revision=1, parent_id=other["id"]))
    store.update(child["id"], TaskPatch(revision=1, parent_id=None))
    store.delete(parent["id"], 1)
