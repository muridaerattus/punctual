def test_http_auth_validation_and_conflicts(client, auth):
    for path in ("/api/tasks", "/mcp/", "/openapi.json"):
        assert client.get(path).status_code == 401
    assert (
        client.post("/api/tasks", headers=auth, json={"title": "  "}).status_code == 422
    )
    assert (
        client.post(
            "/api/tasks", headers=auth, json={"title": "Test", "status": "Done"}
        ).status_code
        == 422
    )
    task = client.post("/api/tasks", headers=auth, json={"title": "HTTP"}).json()
    path = f"/api/tasks/{task['id']}"
    assert (
        client.patch(
            path, headers=auth, json={"revision": 1, "status": "In Progress"}
        ).status_code
        == 200
    )
    assert (
        client.patch(path, headers=auth, json={"revision": 1, "title": "Stale"}).json()[
            "error"
        ]["code"]
        == "revision_conflict"
    )
    lease = client.post(path + "/claim", headers=auth, json={"owner": "agent"}).json()
    assert (
        client.patch(
            path, headers=auth, json={"revision": 2, "title": "Blocked"}
        ).json()["error"]["code"]
        == "task_locked"
    )
    assert (
        client.patch(
            path,
            headers=auth,
            json={"revision": 2, "title": None, "lease_token": lease["lease_token"]},
        ).status_code
        == 422
    )
    assert (
        client.request(
            "DELETE",
            path,
            headers=auth,
            json={"revision": 2, "lease_token": lease["lease_token"]},
        ).status_code
        == 200
    )
