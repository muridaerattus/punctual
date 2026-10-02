from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from punctual.tasks.errors import Conflict
from punctual.tasks.schemas import BoardInput, ForceReleaseInput, TaskInput, TaskPatch


def test_key_mutations_preserve_hierarchy_and_revision_checks(store):
    store.create(TaskInput(title="Unrelated"))
    board = store.create_board(BoardInput(name="Engineering", prefix="ENG"))
    parent = store.create(TaskInput(title="Parent", board_id=board["id"]))
    child = store.create(
        TaskInput(title="Child", board_id=board["id"], parent_id=parent["id"])
    )
    for changes in (
        {"parent_id": parent["id"]},
        {"parent_id": child["id"]},
    ):
        with pytest.raises(Conflict) as exc:
            store.update(parent["key"], TaskPatch(revision=1, **changes))
        assert exc.value.code == "invalid_parent"
    with pytest.raises(Conflict) as exc:
        store.delete(parent["key"], 1)
    assert exc.value.code == "has_subtasks"
    with pytest.raises(Conflict) as exc:
        store.update(child["key"], TaskPatch(revision=2, title="Stale"))
    assert exc.value.code == "revision_conflict"
    store.update(child["key"], TaskPatch(revision=1, parent_id=None))
    assert store.delete(parent["key"], 1) == {"deleted": parent["id"]}


def test_key_and_numeric_claimants_compete_for_same_task(store):
    task = store.create(TaskInput(title="Contended"))
    barrier = Barrier(2)

    def claim(reference, owner):
        barrier.wait()
        try:
            return store.lease(reference, "claim", owner=owner)
        except Conflict as exc:
            return exc.code

    with ThreadPoolExecutor(2) as executor:
        futures = [
            executor.submit(claim, ref, owner)
            for ref, owner in (
                (task["id"], "numeric"),
                (task["key"], "key"),
            )
        ]
        results = [future.result() for future in futures]
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "task_locked" in results
    assert store.get(task["id"])["revision"] == 1


def test_key_force_release_cannot_override_replaced_claim(store):
    task = store.create(TaskInput(title="Reclaimed"))
    first = store.lease(task["key"], "claim", owner="one")
    store.lease(task["key"], "release", token=first["lease_token"])
    second = store.lease(task["key"], "claim", owner="two")
    with pytest.raises(Conflict) as exc:
        store.force_release(
            task["key"],
            ForceReleaseInput(
                revision=1,
                lease_id=first["lease_id"],
                reason="Stale recovery",
            ),
        )
    assert exc.value.code == "lease_conflict"
    assert store.get(task["id"])["lease_id"] == second["lease_id"]


def test_context_by_numeric_id_matches_key_context(store):
    parent = store.create(TaskInput(title="Parent", description="Full details"))
    child = store.create(TaskInput(title="Child", parent_id=parent["id"]))
    keyed = store.get_task_context(child["key"])
    numbered = store.get_task_context(child["id"])
    assert {k: v for k, v in keyed.items() if k != "as_of"} == {
        k: v for k, v in numbered.items() if k != "as_of"
    }
    assert numbered["parent"]["description"] == "Full details"
