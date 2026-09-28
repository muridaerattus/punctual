import json


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


def test_validation_errors_handle_invalid_unicode_without_echoing_secrets(client, auth):
    response = client.patch(
        "/api/tasks/1",
        headers={**auth, "Content-Type": "application/json"},
        content=json.dumps(
            {"revision": "secret-value", "lease_token": "\ud800", "\ud800": "extra"}
        ),
    )
    assert response.status_code == 422
    errors = response.json()["detail"]
    # An invalid field name rejects the whole input before field-level validation.
    assert {error["type"] for error in errors} == {"string_unicode"}
    assert all(set(error) == {"type", "loc", "msg"} for error in errors)
    assert "secret-value" not in response.text
