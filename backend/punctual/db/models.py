from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Board(Base):
    __tablename__ = "boards"
    __table_args__ = (
        CheckConstraint(
            "length(prefix) BETWEEN 1 AND 8 AND prefix NOT GLOB '*[^A-Z]*'",
            name="board_prefix",
        ),
        CheckConstraint("next_number > 0", name="board_sequence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(8), unique=True)
    next_number: Mapped[int] = mapped_column(default=1)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('To Do', 'In Progress', 'Complete')",
            name="task_status",
        ),
        Index("tasks_parent", "parent_id"),
        UniqueConstraint("board_id", "number", name="task_board_number"),
        CheckConstraint("number > 0", name="task_number"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id", ondelete="RESTRICT"))
    number: Mapped[int] = mapped_column()
    board: Mapped[Board] = relationship()
    parent: Mapped["Task | None"] = relationship(remote_side=[id])
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20))
    assignee: Mapped[str | None] = mapped_column(String(100))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="RESTRICT")
    )
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_token: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[float | None] = mapped_column(Float)
    lease_id: Mapped[str | None] = mapped_column(String(32))


class LeaseRelease(Base):
    """Durable forced-release history; retained even when a task is deleted."""

    __tablename__ = "lease_releases"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(index=True)
    revision: Mapped[int] = mapped_column()
    lease_id: Mapped[str] = mapped_column(String(32))
    lease_owner: Mapped[str] = mapped_column(String(100))
    released_at: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(1000))
