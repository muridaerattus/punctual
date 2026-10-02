"""Exercise workflow routes against the same state as the atomic HTTP API."""


def test_http_workflow_lifecycle_and_replay(client, auth):
    task = client.post(
        "/api/tasks",
        headers=auth,
        json={"title": "Implement workflow", "assignee": "human"},
    ).json()
    path = f"/api/workflows/tasks/{task['key']}"
    start = {
        "revision": task["revision"],
        "owner": "agent",
        "lease_token": "s" * 43,
        "request_id": "a" * 43,
    }
    response = client.post(path + "/start", headers=auth, json=start)
    assert response.status_code == 200, response.text
    started = response.json()
    assert started["task"]["status"] == "In Progress"
    assert started["task"]["assignee"] == "human"
    assert started["task"]["revision"] == task["revision"] + 1
    assert started["replayed"] is False
    assert "lease_token" not in started["task"]
    replay = client.post(path + "/start", headers=auth, json=start)
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["task"] == started["task"]

    locked = client.patch(
        f"/api/tasks/{task['id']}",
        headers=auth,
        json={"revision": started["task"]["revision"], "title": "Competing edit"},
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "task_locked"
    finish = {
        "revision": started["task"]["revision"],
        "lease_token": start["lease_token"],
        "request_id": "b" * 43,
    }
    response = client.post(path + "/complete", headers=auth, json=finish)
    assert response.status_code == 200, response.text
    done = response.json()["task"]
    assert done["status"] == "Complete"
    assert done["lease_owner"] is None
    assert done["revision"] == task["revision"] + 2
    assert client.post(path + "/complete", headers=auth, json=finish).json()["replayed"]
    assert client.get(f"/api/tasks/{task['id']}", headers=auth).json() == done


def test_http_workflow_queries_and_validation(client, auth):
    for title in ("First", "Second", "Third"):
        client.post(
            "/api/tasks", headers=auth, json={"title": title, "description": "Long"}
        )
    path = "/api/workflows/tasks"
    response = client.get(path, headers=auth, params={"board": "PUN", "limit": 2})
    assert response.status_code == 200, response.text
    page = response.json()
    assert len(page["items"]) == 2
    assert page["truncated"] is True
    assert all("description" not in task for task in page["items"])
    next_page = client.get(
        path,
        headers=auth,
        params={"board": "PUN", "limit": 2, "cursor": page["next_cursor"]},
    ).json()
    assert len(next_page["items"]) == 1
    assert next_page["truncated"] is False
    for params in ({"limit": 101}, {"limit": 0}, {"cursor": 0}):
        assert (
            client.get(
                path, headers=auth, params={"board": "PUN", **params}
            ).status_code
            == 422
        )
    assert client.get(path, params={"board": "PUN"}).status_code == 401
    for prefix in ("AAA", "BBB"):
        client.post(
            "/api/boards", headers=auth, json={"name": "Duplicate", "prefix": prefix}
        )
    ambiguous = client.get(path, headers=auth, params={"board": "Duplicate"})
    assert ambiguous.status_code == 409
    assert "details" in ambiguous.json()["error"]


def test_http_tree_creation_is_retryable_and_context_is_shared(client, auth):
    data = {
        "board": "PUN",
        "request_id": "c" * 43,
        "parent": {"title": "Project"},
        "children": [{"title": "One"}, {"title": "Two"}],
    }
    response = client.post("/api/workflows/task-trees", headers=auth, json=data)
    assert response.status_code == 200, response.text
    created = response.json()
    assert len(created["children"]) == 2
    assert client.post("/api/workflows/task-trees", headers=auth, json=data).json()[
        "replayed"
    ]
    assert len(client.get("/api/tasks", headers=auth).json()) == 3
    key = created["parent"]["key"]
    context = client.get(
        f"/api/workflows/tasks/{key}/context", headers=auth, params={"limit": 1}
    ).json()
    assert context["task"]["title"] == "Project"
    assert len(context["subtasks"]) == 1
    assert context["truncated"] is True
    assert (
        client.get(
            "/api/workflows/boards/overview",
            headers=auth,
            params={"board": "PUN", "limit": 1},
        ).status_code
        == 200
    )
    available = client.get(
        "/api/workflows/available-work", headers=auth, params={"board": "PUN"}
    ).json()
    assert len(available["items"]) == 3
