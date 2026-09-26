def test_stateless_mcp_and_shared_locking(client, auth):
    headers = {
        **auth,
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2026-07-28",
    }

    def rpc(method, params):
        params["_meta"] = {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        }
        request_headers = {**headers, "Mcp-Method": method}
        if "name" in params:
            request_headers["Mcp-Name"] = params["name"]
        response = client.post(
            "/mcp/",
            headers=request_headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params,
            },
        )
        assert response.status_code == 200, response.text
        assert "mcp-session-id" not in response.headers
        return response.json()

    assert "result" in rpc("server/discover", {})
    names = {tool["name"] for tool in rpc("tools/list", {})["result"]["tools"]}
    assert names == {
        "list_boards",
        "create_board",
        "get_task_by_key",
        "list_tasks",
        "get_task",
        "create_task",
        "update_task",
        "delete_task",
        "claim_task",
        "renew_lease",
        "release_lease",
        "force_release_lease",
    }

    def call(name, arguments):
        return rpc("tools/call", {"name": name, "arguments": arguments})["result"][
            "structuredContent"
        ]

    board = call("create_board", {"board": {"name": "Engineering", "prefix": "ENG"}})[
        "data"
    ]
    assert board in call("list_boards", {})["data"]
    other = call(
        "create_task", {"task": {"title": "Other board", "board_id": board["id"]}}
    )["data"]
    assert other["key"] == "ENG-1"
    assert call("list_tasks", {})["data"] == []
    assert call("list_tasks", {"board_id": board["id"]})["data"] == [other]
    assert call("get_task_by_key", {"key": "ENG-1"})["data"] == other
    created = rpc(
        "tools/call",
        {
            "name": "create_task",
            "arguments": {"task": {"title": "MCP task"}},
        },
    )["result"]["structuredContent"]
    task = created["data"]
    claimed = rpc(
        "tools/call",
        {
            "name": "claim_task",
            "arguments": {"task_id": task["id"], "owner": "mcp-agent"},
        },
    )["result"]["structuredContent"]
    assert claimed["ok"]
    response = client.patch(
        f"/api/tasks/{task['id']}",
        headers=auth,
        json={"revision": 1, "status": "Complete"},
    )
    assert response.json()["error"]["code"] == "task_locked"
    updated = rpc(
        "tools/call",
        {
            "name": "update_task",
            "arguments": {
                "task_id": task["id"],
                "changes": {
                    "revision": 1,
                    "lease_token": claimed["data"]["lease_token"],
                    "status": "Complete",
                },
            },
        },
    )["result"]["structuredContent"]
    assert updated["data"]["status"] == "Complete"
    rejected = rpc(
        "tools/call",
        {
            "name": "delete_task",
            "arguments": {"task_id": task["id"], "revision": 2},
        },
    )["result"]["structuredContent"]
    assert rejected == {
        "ok": False,
        "error": {"code": "task_locked", "message": "Task is claimed by mcp-agent"},
    }
    released = rpc(
        "tools/call",
        {
            "name": "force_release_lease",
            "arguments": {
                "task_id": task["id"],
                "release": {
                    "revision": 2,
                    "lease_id": claimed["data"]["lease_id"],
                    "reason": "Recover lost token",
                },
            },
        },
    )["result"]["structuredContent"]
    assert released["ok"]
    assert released["data"]["lease_id"] is None
    assert (
        client.get(f"/api/tasks/{task['id']}/lease-history", headers=auth).json()[0][
            "reason"
        ]
        == "Recover lost token"
    )
    assert (
        client.post(
            "/mcp/", headers={**headers, "Origin": "https://untrusted.example"}, json={}
        ).status_code
        == 403
    )
