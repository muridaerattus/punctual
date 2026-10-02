"""Outcome-oriented HTTP adapters sharing the MCP workflow service."""

from typing import Annotated

from fastapi import APIRouter, Query

from ..tasks.schemas import Status
from ..tasks.service import TaskService
from ..tasks.write_schemas import CompleteTaskInput, StartTaskInput, TaskTreeInput

Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[int | None, Query(gt=0)]


def workflow_router(store: TaskService):
    router = APIRouter(prefix="/api/workflows", tags=["workflows"])

    @router.get("/tasks")
    def query_tasks(
        board: str,
        status: Status | None = None,
        assignee: str | None = None,
        query: str | None = None,
        parent_id: Annotated[int | None, Query(gt=0)] = None,
        available: bool | None = None,
        limit: Limit = 50,
        cursor: Cursor = None,
    ):
        return store.query_tasks(
            board, status, assignee, query, parent_id, available, limit, cursor
        )

    @router.get("/tasks/{key}/context")
    def task_context(key: str, limit: Limit = 50, cursor: Cursor = None):
        return store.get_task_context(key, limit, cursor)

    @router.get("/boards/overview")
    def board_overview(board: str, limit: Limit = 10):
        return store.board_overview(board, limit)

    @router.get("/available-work")
    def available_work(
        board: str,
        assignee: str | None = None,
        query: str | None = None,
        limit: Limit = 50,
        cursor: Cursor = None,
    ):
        return store.find_available_work(board, assignee, query, limit, cursor)

    @router.get("/tasks/{task_id}/lease-history")
    def lease_history(task_id: int, limit: Limit = 50, cursor: Cursor = None):
        return store.get_lease_history(task_id, limit, cursor)

    @router.post("/tasks/{key}/start")
    def start_task(key: str, data: StartTaskInput):
        return store.start_task(key, data)

    @router.post("/tasks/{key}/complete")
    def complete_task(key: str, data: CompleteTaskInput):
        return store.complete_task(key, data)

    @router.post("/task-trees")
    def create_task_tree(data: TaskTreeInput):
        return store.create_task_tree(data)

    return router
