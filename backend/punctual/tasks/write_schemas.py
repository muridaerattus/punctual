from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .schemas import Status

RequestID = Annotated[
    str, Field(min_length=32, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
]


class StartTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)
    owner: str = Field(min_length=1, max_length=100, pattern=r"\S")
    lease_token: RequestID
    request_id: RequestID
    seconds: int = Field(default=900, ge=30, le=86400)
    assignee: str | None = Field(default=None, max_length=100)


class CompleteTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)
    lease_token: str = Field(
        min_length=1,
        description="Owned active lease token, including tokens preserved by migration",
    )
    request_id: RequestID


class TreeTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=50000)
    status: Status = "To Do"
    assignee: str | None = Field(default=None, max_length=100)


class TaskTreeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    board: str = Field(min_length=1, max_length=100, pattern=r"\S")
    parent: TreeTaskInput
    children: list[TreeTaskInput] = Field(default_factory=list, max_length=50)
    request_id: RequestID
