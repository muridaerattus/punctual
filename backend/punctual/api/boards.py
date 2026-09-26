from fastapi import APIRouter

from ..tasks.schemas import BoardInput
from ..tasks.service import TaskService


def board_router(store: TaskService):
    router = APIRouter(prefix="/api/boards", tags=["boards"])

    @router.get("")
    def boards():
        return store.list_boards()

    @router.post("", status_code=201)
    def create(board: BoardInput):
        return store.create_board(board)

    return router
