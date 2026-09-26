from fastapi import APIRouter

from ..tasks.errors import Conflict
from ..tasks.schemas import (
    DeleteInput,
    ForceReleaseInput,
    LeaseInput,
    Status,
    TaskInput,
    TaskPatch,
)
from ..tasks.service import TaskService


def task_router(store: TaskService):
    router = APIRouter(prefix="/api/tasks", tags=["tasks"])

    @router.get("")
    def tasks(
        status: Status | None = None,
        assignee: str | None = None,
        query: str | None = None,
        board_id: int = 1,
    ):
        return store.list(status, assignee, query, board_id)

    @router.post("", status_code=201)
    def create(task: TaskInput):
        return store.create(task)

    @router.get("/by-key/{key}")
    def get_by_key(key: str):
        return store.get_by_key(key)

    @router.get("/{task_id}")
    def get(task_id: int):
        return store.get(task_id)

    @router.patch("/{task_id}")
    def update(task_id: int, changes: TaskPatch):
        return store.update(task_id, changes)

    @router.delete("/{task_id}")
    def delete(task_id: int, body: DeleteInput):
        return store.delete(task_id, body.revision, body.lease_token)

    @router.post("/{task_id}/force-release")
    def force_release(task_id: int, body: ForceReleaseInput):
        return store.force_release(task_id, body)

    @router.get("/{task_id}/lease-history")
    def lease_history(task_id: int):
        return store.lease_history(task_id)

    @router.post("/{task_id}/{action}")
    def lease(task_id: int, action: str, body: LeaseInput):
        if action not in ("claim", "renew", "release"):
            raise Conflict("not_found", "Unknown action", 404)
        return store.lease(
            task_id,
            action,
            owner=body.owner,
            token=body.lease_token,
            seconds=body.seconds,
        )

    return router
