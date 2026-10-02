"""Exact task references resolved inside the caller's transaction."""

import re
from typing import Annotated

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Board, Task
from .errors import Conflict

MAX_ID = 9223372036854775807
KEY_PATTERN = r"^[A-Z]{1,8}-[1-9][0-9]*$"
TaskReference = Annotated[
    Annotated[int, Field(gt=0, le=MAX_ID, strict=True)]
    | Annotated[str, Field(pattern=KEY_PATTERN)],
    Field(
        description="Exact ticket key such as ENG-123, or a positive numeric task ID"
    ),
]


def task_condition(reference: int | str):
    if type(reference) is int:
        if not 1 <= reference <= MAX_ID:
            raise Conflict(
                "invalid_task", "Task ID must be a positive SQLite row ID", 422
            )
        return Task.id == reference
    if not isinstance(reference, str) or not re.fullmatch(KEY_PATTERN, reference):
        raise Conflict(
            "invalid_key",
            "Expected a ticket key such as PUN-123 or a numeric task ID",
            422,
        )
    prefix, number = reference.split("-")
    if len(number) > 19 or int(number) > MAX_ID:
        raise Conflict("not_found", "Task not found", 404)
    board_id = select(Board.id).where(Board.prefix == prefix).scalar_subquery()
    return (Task.board_id == board_id) & (Task.number == int(number))


def resolve_task(session: Session, reference: int | str) -> Task:
    task = session.scalar(select(Task).where(task_condition(reference)))
    if task is None:
        raise Conflict("not_found", "Task not found", 404)
    return task
