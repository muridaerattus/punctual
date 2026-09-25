import time

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db.models import LeaseRelease, Task
from ..db.session import Database
from . import leases
from .errors import Conflict
from .schemas import ForceReleaseInput, TaskInput, TaskPatch


def public(task: Task):
    result = {
        column.name: getattr(task, column.name)
        for column in Task.__table__.columns
        if column.name != "lease_token"
    }
    if not leases.active(task):
        result["lease_owner"] = result["lease_expires_at"] = None
        result["lease_id"] = None
    return result


class TaskService:
    """Task use cases shared by HTTP and MCP, each with a short ORM transaction."""

    def __init__(self, path: str):
        self.path = path
        self.database = Database(path)

    @staticmethod
    def task(session: Session, task_id: int) -> Task:
        task = session.get(Task, task_id)
        if task is None:
            raise Conflict("not_found", "Task not found", 404)
        return task

    @staticmethod
    def has_children(session: Session, task_id: int) -> bool:
        return (
            session.scalar(select(Task.id).where(Task.parent_id == task_id).limit(1))
            is not None
        )

    def validate_parent(
        self, session: Session, parent_id: int | None, task_id: int | None = None
    ):
        if parent_id is None:
            return
        parent = self.task(session, parent_id)
        if parent_id == task_id or parent.parent_id is not None:
            raise Conflict("invalid_parent", "Subtasks support one level only", 422)
        if task_id and self.has_children(session, task_id):
            raise Conflict(
                "invalid_parent", "A task with subtasks cannot become a subtask", 422
            )

    def get(self, task_id: int):
        with self.database.session() as session:
            return public(self.task(session, task_id))

    def list(self, status=None, assignee=None, query=None):
        statement = select(Task).order_by(Task.id)
        if status is not None:
            statement = statement.where(Task.status == status)
        if assignee is not None:
            statement = statement.where(Task.assignee == assignee)
        if query:
            statement = statement.where(
                or_(
                    func.instr(func.lower(Task.title), func.lower(query)) > 0,
                    func.instr(func.lower(Task.description), func.lower(query)) > 0,
                )
            )
        with self.database.session() as session:
            return [public(task) for task in session.scalars(statement)]

    def create(self, data: TaskInput):
        with self.database.session(write=True) as session:
            self.validate_parent(session, data.parent_id)
            task = Task(
                **data.model_dump(), created_at=time.time(), updated_at=time.time()
            )
            session.add(task)
            session.flush()
            return public(task)

    def update(self, task_id: int, data: TaskPatch):
        with self.database.session(write=True) as session:
            task = self.task(session, task_id)
            leases.guard(task, data.revision, data.lease_token)
            changes = data.model_dump(
                exclude_unset=True, exclude={"revision", "lease_token"}
            )
            for field in ("title", "description", "status"):
                if field in changes and changes[field] is None:
                    raise Conflict("invalid_field", f"{field} cannot be null", 422)
            if "parent_id" in changes:
                self.validate_parent(session, changes["parent_id"], task_id)
            for field, value in changes.items():
                setattr(task, field, value)
            task.revision += 1
            task.updated_at = time.time()
            session.flush()
            return public(task)

    def delete(self, task_id: int, revision: int, token: str | None = None):
        with self.database.session(write=True) as session:
            task = self.task(session, task_id)
            leases.guard(task, revision, token)
            if self.has_children(session, task_id):
                raise Conflict("has_subtasks", "Delete or detach subtasks first")
            session.delete(task)
            return {"deleted": task_id}

    def lease(self, task_id: int, action: str, owner=None, token=None, seconds=900):
        with self.database.session(write=True) as session:
            task = self.task(session, task_id)
            leases.change(task, action, owner, token, seconds)
            session.flush()
            result = public(task)
            if task.lease_token:
                result["lease_token"] = task.lease_token
            return result

    def force_release(self, task_id: int, data: ForceReleaseInput):
        with self.database.session(write=True) as session:
            task = self.task(session, task_id)
            if task.revision != data.revision:
                raise Conflict(
                    "revision_conflict", "Task changed; fetch it again before releasing"
                )
            if not leases.active(task) or task.lease_id != data.lease_id:
                raise Conflict(
                    "lease_conflict", "Lease changed or expired; fetch the task again"
                )
            session.add(
                LeaseRelease(
                    task_id=task.id,
                    revision=task.revision,
                    lease_id=task.lease_id,
                    lease_owner=task.lease_owner,
                    released_at=time.time(),
                    reason=data.reason,
                )
            )
            task.lease_owner = task.lease_token = task.lease_id = (
                task.lease_expires_at
            ) = None
            session.flush()
            return public(task)

    def lease_history(self, task_id: int):
        with self.database.session() as session:
            events = session.scalars(
                select(LeaseRelease)
                .where(LeaseRelease.task_id == task_id)
                .order_by(LeaseRelease.id)
            )
            return [
                {
                    column.name: getattr(event, column.name)
                    for column in LeaseRelease.__table__.columns
                }
                for event in events
            ]
