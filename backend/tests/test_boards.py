from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from punctual.tasks.errors import Conflict
from punctual.tasks.schemas import BoardInput, TaskInput, TaskPatch
from punctual.tasks.service import TaskService


@pytest.mark.parametrize(
    "prefix", ["", "lower", "ABCDEFGHI", "A1", "A-B", "É", " A", "A ", "A\n"]
)
def test_invalid_prefix(prefix):
    with pytest.raises(ValidationError):
        BoardInput(name="Board", prefix=prefix)


def test_board_sequences_scoping_and_stable_keys(store):
    board = store.create_board(BoardInput(name="Engineering", prefix="ABCDEFGH"))
    with pytest.raises(Conflict, match="prefix already exists"):
        store.create_board(BoardInput(name="Duplicate", prefix="ABCDEFGH"))
    default = store.create(TaskInput(title="Default task"))
    other = store.create(TaskInput(title="Other task", board_id=board["id"]))
    assert (default["key"], other["key"]) == ("PUN-1", "ABCDEFGH-1")
    assert default["id"] != other["id"]
    assert store.list() == [default]
    assert store.list(board_id=board["id"], query="abcdefgh-1") == [other]
    store.update(other["id"], TaskPatch(revision=1, title="Renamed"))
    assert store.get_by_key(other["key"])["revision"] == 2
    store.delete(other["id"], 2)
    restarted = TaskService(store.path)
    try:
        task = restarted.create(TaskInput(title="Next", board_id=board["id"]))
        assert task["key"] == "ABCDEFGH-2"
        assert task["id"] > other["id"]
    finally:
        restarted.database.engine.dispose()
    for operation in (
        lambda: store.list(board_id=999),
        lambda: store.create(TaskInput(title="Bad", board_id=999)),
        lambda: store.get_by_key(other["key"]),
    ):
        with pytest.raises(Conflict) as exc:
            operation()
        assert exc.value.code == "not_found"


def test_parent_board_validation_and_failed_creation_does_not_consume_number(store):
    board = store.create_board(BoardInput(name="Other", prefix="OTHER"))
    parent = store.create(TaskInput(title="Parent"))
    with pytest.raises(Conflict, match="same board"):
        store.create(
            TaskInput(title="Wrong", board_id=board["id"], parent_id=parent["id"])
        )
    other = store.create(TaskInput(title="Other", board_id=board["id"]))
    assert other["key"] == "OTHER-1"
    with pytest.raises(Conflict, match="same board"):
        store.update(other["id"], TaskPatch(revision=1, parent_id=parent["id"]))
    assert store.get(other["id"])["revision"] == 1
    child = store.create(
        TaskInput(title="Child", board_id=board["id"], parent_id=other["id"])
    )
    assert child["parent_key"] == "OTHER-1"
    with pytest.raises(Conflict, match="one level"):
        store.create(
            TaskInput(title="Grandchild", board_id=board["id"], parent_id=child["id"])
        )


def test_concurrent_board_numbers(store):
    board = store.create_board(BoardInput(name="Concurrent", prefix="CON"))

    def create(i):
        return store.create(TaskInput(title=f"Task {i}", board_id=board["id"]))

    with ThreadPoolExecutor(max_workers=6) as pool:
        tasks = list(pool.map(create, range(18)))
    assert sorted(t["number"] for t in tasks) == list(range(1, 19))
    assert len({t["key"] for t in tasks}) == 18


def test_http_boards(client, auth):
    assert client.get("/api/boards").status_code == 401
    assert (
        client.post(
            "/api/boards", headers=auth, json={"name": "Bad", "prefix": "bad"}
        ).status_code
        == 422
    )
    data = {"name": "Engineering", "prefix": "ENG"}
    board = client.post("/api/boards", headers=auth, json=data)
    assert board.status_code == 201
    assert client.post("/api/boards", headers=auth, json=data).status_code == 409
    assert len(client.get("/api/boards", headers=auth).json()) == 2
    task = client.post(
        "/api/tasks",
        headers=auth,
        json={"title": "Scoped", "board_id": board.json()["id"]},
    ).json()
    assert client.get("/api/tasks", headers=auth).json() == []
    assert client.get(
        f"/api/tasks?board_id={board.json()['id']}", headers=auth
    ).json() == [task]
    assert client.get("/api/tasks/by-key/ENG-1", headers=auth).json() == task
    assert client.get("/api/tasks/by-key/ENG-01", headers=auth).status_code == 422
    assert client.get("/api/tasks/by-key/ENG-999", headers=auth).status_code == 404
    assert (
        client.patch(
            f"/api/tasks/{task['id']}",
            headers=auth,
            json={"revision": 1, "board_id": 1},
        ).status_code
        == 422
    )
