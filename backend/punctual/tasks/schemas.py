from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["To Do", "In Progress", "Complete"]


class BoardInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100, pattern=r"\S")
    prefix: str = Field(pattern=r"^[A-Z]{1,8}$", max_length=8)


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=50000)
    status: Status = "To Do"
    assignee: str | None = Field(default=None, max_length=100)
    parent_id: int | None = Field(default=None, gt=0)
    board_id: int = Field(default=1, gt=0)


class TaskPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    revision: int = Field(ge=1)
    lease_token: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=50000)
    status: Status | None = None
    assignee: str | None = Field(default=None, max_length=100)
    parent_id: int | None = Field(default=None, gt=0)


class LeaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str | None = None
    lease_token: str | None = None
    seconds: int = Field(default=900, ge=30, le=86400)


class DeleteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)
    lease_token: str | None = None


class ForceReleaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    revision: int = Field(ge=1)
    lease_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    reason: str = Field(min_length=1, max_length=1000)
