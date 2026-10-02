"""Atomic writes with durable, historical public-result replay.

A replay is an as-of-success snapshot, not a current task read. It never renews
leases, reapplies changes, or returns credentials, even after task deletion.
Request IDs are global across operations and must not be reused for new work.
"""

import hashlib
import json
import re
import time

from sqlalchemy import select

from ..db.idempotency_models import IdempotencyReceipt
from ..db.models import Board, Task
from . import leases
from .errors import Conflict
from .write_schemas import CompleteTaskInput, StartTaskInput, TaskTreeInput


def fingerprint(operation, data, key=None):
    payload = data.model_dump(exclude={"request_id"})
    if "lease_token" in payload:
        payload["lease_token"] = hashlib.sha256(
            payload["lease_token"].encode()
        ).hexdigest()
    if isinstance(data, StartTaskInput):
        payload["assignee_supplied"] = "assignee" in data.model_fields_set
    encoded = json.dumps(
        {"operation": operation, "key": key, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def replay(session, request_id, operation, digest):
    receipt = session.get(IdempotencyReceipt, request_id)
    if receipt is None:
        return None
    if receipt.operation != operation or receipt.fingerprint != digest:
        raise Conflict(
            "request_conflict",
            "Request ID already used for a different operation or payload",
        )
    return {**json.loads(receipt.outcome), "replayed": True}


def record(session, request_id, operation, digest, result):
    session.add(
        IdempotencyReceipt(
            request_id=request_id,
            operation=operation,
            fingerprint=digest,
            outcome=json.dumps(result, sort_keys=True),
            created_at=time.time(),
        )
    )
    session.flush()
    return {**result, "replayed": False}


def task_by_key(session, key):
    if not re.fullmatch(r"[A-Z]{1,8}-[1-9][0-9]*", key):
        raise Conflict("invalid_key", "Expected a ticket key such as PUN-123", 422)
    prefix, number = key.split("-")
    task = (
        session.scalar(
            select(Task)
            .join(Board)
            .where(Board.prefix == prefix, Task.number == int(number))
        )
        if len(number) <= 19 and int(number) <= 9223372036854775807
        else None
    )
    if task is None:
        raise Conflict("not_found", "Task not found", 404)
    return task


class WriteWorkflows:
    def start_task(self, key: str, data: StartTaskInput):
        """Claim and start; preserve assignment unless supplied, reject Complete."""
        from .service import public

        operation = "start_task"
        digest = fingerprint(operation, data, key)
        with self.database.session(write=True) as session:
            previous = replay(session, data.request_id, operation, digest)
            if previous is not None:
                return previous
            task = task_by_key(session, key)
            leases.guard(task, data.revision, data.lease_token)
            if task.status == "Complete":
                raise Conflict(
                    "invalid_status", "Completed tasks must be reopened explicitly"
                )
            leases.change(task, "claim", data.owner, data.lease_token, data.seconds)
            task.status = "In Progress"
            if "assignee" in data.model_fields_set:
                task.assignee = data.assignee
            task.revision += 1
            task.updated_at = time.time()
            session.flush()
            return record(
                session, data.request_id, operation, digest, {"task": public(task)}
            )

    def complete_task(self, key: str, data: CompleteTaskInput):
        """Complete and release an active owned lease; children are independent."""
        from .service import public

        operation = "complete_task"
        digest = fingerprint(operation, data, key)
        with self.database.session(write=True) as session:
            previous = replay(session, data.request_id, operation, digest)
            if previous is not None:
                return previous
            task = task_by_key(session, key)
            leases.guard(task, data.revision, data.lease_token)
            leases.change(task, "release", None, data.lease_token, 900)
            task.status = "Complete"
            task.revision += 1
            task.updated_at = time.time()
            session.flush()
            return record(
                session, data.request_id, operation, digest, {"task": public(task)}
            )

    def create_task_tree(self, data: TaskTreeInput):
        """Create a parent and up to 50 children with consecutive board numbers."""
        from .reads import resolve_board
        from .service import public

        operation = "create_task_tree"
        digest = fingerprint(operation, data)
        with self.database.session(write=True) as session:
            previous = replay(session, data.request_id, operation, digest)
            if previous is not None:
                return previous
            board = resolve_board(session, data.board)
            now = time.time()

            def create(item, parent=None):
                task = Task(
                    **item.model_dump(),
                    board=board,
                    number=board.next_number,
                    parent=parent,
                    created_at=now,
                    updated_at=now,
                )
                board.next_number += 1
                session.add(task)
                session.flush()
                return task

            parent = create(data.parent)
            children = [create(child, parent) for child in data.children]
            return record(
                session,
                data.request_id,
                operation,
                digest,
                {"parent": public(parent), "children": [public(t) for t in children]},
            )
