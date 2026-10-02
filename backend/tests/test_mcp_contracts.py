import asyncio
import json

import jsonschema
import pytest
from fastmcp import Client

from punctual.db.models import Task as TaskRecord
from punctual.mcp.server import create_mcp
from punctual.tasks.schemas import BoardInput, TaskInput

TOKEN = "mcp-contract-token-" + "a" * 32
REQUEST = "mcp-contract-request-" + "b" * 32


def run(store, scenario):
    async def connected():
        async with Client(create_mcp(store)) as client:
            return await scenario(client)

    return asyncio.run(connected())


async def checked(client, name, arguments, *, error=False):
    response = await client.call_tool(name, arguments, raise_on_error=False)
    assert response.is_error is error
    payload = response.structured_content
    assert payload["ok"] is not error
    # Old text-only consumers see the same recognizable envelope.
    assert json.loads(response.content[0].text) == payload
    tool = next(t for t in await client.list_tools() if t.name == name)
    jsonschema.validate(payload, tool.output_schema)
    return payload


def test_metadata_and_schema_constraints(store):
    async def scenario(client):
        tools = {t.name: t for t in await client.list_tools()}
        reads = {
            "list_boards",
            "query_tasks",
            "get_task_context",
            "board_overview",
            "find_available_work",
            "get_lease_history",
        }
        assert len(tools) == 17
        assert not {"get_task", "get_task_by_key", "list_tasks"} & tools.keys()
        for name, tool in tools.items():
            annotations = tool.annotations.model_dump(by_alias=True)
            assert annotations["readOnlyHint"] is (name in reads)
            assert annotations["openWorldHint"] is False
            assert type(annotations["destructiveHint"]) is bool
            assert type(annotations["idempotentHint"]) is bool
            assert tool.output_schema["type"] == "object"
            assert "data" in tool.output_schema["properties"]
            assert "error" in tool.output_schema["properties"]
        claim = tools["claim_task"].input_schema["properties"]
        assert claim["task_id"]["anyOf"][0]["exclusiveMinimum"] == 0
        assert claim["task_id"]["anyOf"][1]["pattern"]
        assert claim["owner"]["minLength"] == 1
        assert claim["owner"]["maxLength"] == 100
        assert claim["owner"]["pattern"] == r"\S"
        assert claim["seconds"]["minimum"] == 30
        assert claim["seconds"]["maximum"] == 86400
        token = claim["lease_token"]["anyOf"][0]
        assert token["minLength"] == 32 and token["maxLength"] == 100
        for name in ("query_tasks", "find_available_work", "board_overview"):
            assert "board" in tools[name].input_schema["required"]
        for name in ("start_task", "complete_task", "create_task_tree"):
            assert tools[name].annotations.idempotent_hint

    run(store, scenario)


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("get_task_context", {"key": 0}),
        ("get_task_context", {"key": 2**63}),
        ("get_task_context", {"key": True}),
        ("get_task_context", {"key": "123"}),
        ("delete_task", {"task_id": 1, "revision": 0}),
        ("claim_task", {"task_id": 1, "owner": " "}),
        ("claim_task", {"task_id": 1, "owner": "x" * 101}),
        ("claim_task", {"task_id": 1, "owner": "agent", "seconds": 29}),
        ("claim_task", {"task_id": 1, "owner": "agent", "seconds": 86401}),
        ("claim_task", {"task_id": 1, "owner": "agent", "lease_token": "short-secret"}),
        ("renew_lease", {"task_id": 1, "lease_token": "old-token", "seconds": 29}),
        ("query_tasks", {}),
        ("query_tasks", {"board": " "}),
        ("query_tasks", {"board": "PUN", "limit": 101}),
        ("get_task_context", {"key": "some title"}),
        ("get_lease_history", {"task_id": 1, "cursor": 0}),
        ("start_task", {"key": "PUN-1", "data": {"revision": 1, "owner": "a"}}),
    ],
)
def test_invalid_arguments_have_redacted_error_envelopes(store, name, arguments):
    async def scenario(client):
        payload = await checked(client, name, arguments, error=True)
        assert payload["error"]["code"] == "invalid_arguments"
        assert payload["error"]["details"]["fields"]
        assert "short-secret" not in json.dumps(payload)
        assert "!" * 32 not in json.dumps(payload)

    run(store, scenario)


def test_read_workflows_paging_disambiguation_and_redaction(store):
    first = store.create(TaskInput(title="Parent", description="long description"))
    child = store.create(TaskInput(title="Child", parent_id=first["id"]))
    store.lease(first["id"], "claim", owner="reader", token=TOKEN)
    store.create_board(BoardInput(name="Duplicate", prefix="ONE"))
    store.create_board(BoardInput(name="Duplicate", prefix="TWO"))

    async def scenario(client):
        page = (await checked(client, "query_tasks", {"board": "PUN", "limit": 1}))[
            "data"
        ]
        assert page["items"][0]["id"] == first["id"]
        assert page["truncated"] and page["next_cursor"] == first["id"]
        assert "description" not in page["items"][0]
        assert "number" not in page["items"][0]
        assert "as_of" in page
        next_page = (
            await checked(
                client, "query_tasks", {"board": "PUN", "cursor": page["next_cursor"]}
            )
        )["data"]
        assert [t["id"] for t in next_page["items"]] == [child["id"]]
        context = await checked(client, "get_task_context", {"key": child["key"]})
        assert context["data"]["parent"]["description"] == "long description"
        overview = await checked(client, "board_overview", {"board": "PUN", "limit": 1})
        assert overview["data"]["counts"]["total"] == 2
        assert overview["data"]["counts"]["subtasks"]["total"] == 1
        available = await checked(client, "find_available_work", {"board": "PUN"})
        assert [t["id"] for t in available["data"]["items"]] == [child["id"]]
        for payload in (page, next_page, context, overview, available):
            assert TOKEN not in json.dumps(payload)
            assert "lease_token" not in json.dumps(payload)
        ambiguous = await checked(
            client, "query_tasks", {"board": "Duplicate"}, error=True
        )
        assert ambiguous["error"]["code"] == "ambiguous_board"
        assert [b["prefix"] for b in ambiguous["error"]["details"]["candidates"]] == [
            "ONE",
            "TWO",
        ]
        missing = await checked(client, "query_tasks", {"board": "MISSING"}, error=True)
        assert missing["error"]["code"] == "not_found"

    run(store, scenario)


def test_atomic_and_composite_results_and_replays(store):
    async def scenario(client):
        tree_args = {
            "data": {
                "board": "PUN",
                "parent": {"title": "Workflow"},
                "children": [{"title": "Child"}],
                "request_id": REQUEST,
            }
        }
        tree = await checked(client, "create_task_tree", tree_args)
        assert tree["summary"] == "Created PUN-1 with 1 children (replayed=false)."
        replay = await checked(client, "create_task_tree", tree_args)
        assert replay["data"]["replayed"] is True
        task = tree["data"]["children"][0]
        start_args = {
            "key": task["key"],
            "data": {
                "revision": task["revision"],
                "owner": "agent",
                "lease_token": TOKEN,
                "request_id": REQUEST + "s",
            },
        }
        started = await checked(client, "start_task", start_args)
        assert started["data"]["task"]["status"] == "In Progress"
        assert started["data"]["task"]["assignee"] is None
        assert (await checked(client, "start_task", start_args))["data"]["replayed"]
        conflict = await checked(
            client,
            "update_task",
            {"task_id": task["id"], "changes": {"revision": 1, "title": "stale"}},
            error=True,
        )
        assert conflict["error"]["code"] in ("revision_conflict", "task_locked")
        complete_args = {
            "key": task["key"],
            "data": {
                "revision": started["data"]["task"]["revision"],
                "lease_token": TOKEN,
                "request_id": REQUEST + "c",
            },
        }
        completed = await checked(client, "complete_task", complete_args)
        assert completed["data"]["task"]["status"] == "Complete"
        assert completed["data"]["task"]["lease_owner"] is None
        assert (await checked(client, "complete_task", complete_args))["data"][
            "replayed"
        ]
        for payload in (tree, started, completed):
            assert "lease_token" not in json.dumps(payload)
        claimed = await checked(
            client,
            "claim_task",
            {"task_id": task["id"], "owner": "agent", "lease_token": TOKEN},
        )
        assert claimed["data"]["lease_token"] == TOKEN
        renewed = await checked(
            client, "renew_lease", {"task_id": task["id"], "lease_token": TOKEN}
        )
        assert renewed["data"]["lease_token"] == TOKEN
        await checked(
            client,
            "force_release_lease",
            {
                "task_id": task["id"],
                "release": {
                    "revision": completed["data"]["task"]["revision"],
                    "lease_id": claimed["data"]["lease_id"],
                    "reason": "Contract test",
                },
            },
        )
        history = await checked(client, "get_lease_history", {"task_id": task["id"]})
        assert history["data"]["items"][0]["reason"] == "Contract test"

    run(store, scenario)


def test_adapter_projects_private_fields_and_masks_internal_errors(store, monkeypatch):
    task = store.create(TaskInput(title="Projection"))
    context = store.get_task_context(task["key"])

    def leaky_get(key, **kwargs):
        return {
            **context,
            "task": {**task, "lease_token": TOKEN, "request_id": REQUEST},
        }

    monkeypatch.setattr(store, "get_task_context", leaky_get)

    async def scenario(client):
        public = await checked(client, "get_task_context", {"key": task["id"]})
        assert TOKEN not in json.dumps(public)
        assert REQUEST not in json.dumps(public)
        assert "lease_token" not in public["data"]["task"]

        def broken_get(key, **kwargs):
            raise RuntimeError(f"Database secret: {TOKEN}")

        monkeypatch.setattr(store, "get_task_context", broken_get)
        failed = await checked(
            client, "get_task_context", {"key": task["id"]}, error=True
        )
        assert failed == {
            "ok": False,
            "error": {"code": "internal_error", "message": "Tool execution failed"},
        }

    run(store, scenario)


@pytest.mark.parametrize("action", ["renew", "release", "update", "delete", "complete"])
@pytest.mark.parametrize("by_key", [False, True])
def test_mcp_accepts_existing_legacy_lease_tokens(store, action, by_key):
    task = store.create(TaskInput(title="Legacy claim"))
    reference = task["key"] if by_key else task["id"]
    store.lease(task["id"], "claim", owner="legacy-owner")
    with store.database.session(write=True) as session:
        session.get(TaskRecord, task["id"]).lease_token = "old-token"

    async def scenario(client):
        if action == "complete":
            name = "complete_task"
            arguments = {
                "key": task["key"],
                "data": {
                    "revision": 1,
                    "lease_token": "old-token",
                    "request_id": REQUEST,
                },
            }
        elif action == "update":
            name = "update_task"
            arguments = {
                "task_id": reference,
                "changes": {
                    "revision": 1,
                    "lease_token": "old-token",
                    "title": "Edited",
                },
            }
        else:
            name = {
                "renew": "renew_lease",
                "release": "release_lease",
                "delete": "delete_task",
            }[action]
            arguments = {"task_id": reference, "lease_token": "old-token"}
            if action == "delete":
                arguments["revision"] = 1
        result = await checked(client, name, arguments)
        assert result["ok"] is True

    run(store, scenario)


def test_direct_key_claim_recovery_and_history(store):
    unrelated = store.create(TaskInput(title="Default board"))
    board = store.create_board(BoardInput(name="Engineering", prefix="ENG"))
    task = store.create(TaskInput(title="Engineering task", board_id=board["id"]))
    assert task["id"] != task["number"]

    async def scenario(client):
        arguments = {"task_id": task["key"], "owner": "agent", "lease_token": TOKEN}
        claimed = (await checked(client, "claim_task", arguments))["data"]
        recovered = (await checked(client, "claim_task", arguments))["data"]
        assert recovered == claimed
        assert store.get(unrelated["id"])["lease_owner"] is None
        assert claimed["status"] == "To Do"
        released = await checked(
            client,
            "force_release_lease",
            {
                "task_id": task["key"],
                "release": {
                    "revision": 1,
                    "lease_id": claimed["lease_id"],
                    "reason": "Recovery",
                },
            },
        )
        assert released["data"]["lease_owner"] is None
        history = (
            await checked(client, "get_lease_history", {"task_id": task["key"]})
        )["data"]
        assert history["items"][0]["task_id"] == task["id"]
        await checked(client, "delete_task", {"task_id": task["key"], "revision": 1})
        retained = (
            await checked(client, "get_lease_history", {"task_id": task["id"]})
        )["data"]
        assert retained == history
        missing = await checked(
            client, "get_lease_history", {"task_id": task["key"]}, error=True
        )
        assert missing["error"]["code"] == "not_found"

    run(store, scenario)


@pytest.mark.parametrize("name", ["list_tasks", "get_task", "get_task_by_key"])
def test_removed_tools_are_not_callable(store, name):
    async def scenario(client):
        response = await client.call_tool(name, {}, raise_on_error=False)
        assert response.is_error
        assert response.structured_content["error"]["code"] == "not_found"

    run(store, scenario)
