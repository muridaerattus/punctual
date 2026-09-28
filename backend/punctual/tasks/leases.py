import secrets
import time

from ..db.models import Task
from .errors import Conflict


def active(task: Task) -> bool:
    return (task.lease_expires_at or 0) > time.time()


def token_matches(expected: str | None, supplied: str | None) -> bool:
    # compare_digest(str, str) raises on non-ASCII input. Treat it as a mismatch,
    # while still accepting shorter ASCII tokens preserved by legacy migrations.
    return bool(
        expected
        and supplied
        and expected.isascii()
        and supplied.isascii()
        and secrets.compare_digest(expected, supplied)
    )


def guard(task: Task, revision: int, token: str | None):
    if active(task) and not token_matches(task.lease_token, token):
        raise Conflict("task_locked", f"Task is claimed by {task.lease_owner}")
    if task.revision != revision:
        raise Conflict(
            "revision_conflict", "Task changed; fetch it again before editing"
        )


def change(task: Task, action: str, owner: str | None, token: str | None, seconds: int):
    if action not in ("claim", "renew", "release"):
        raise Conflict("invalid_action", "Unknown lease action", 422)
    if not 30 <= seconds <= 86400:
        raise Conflict(
            "invalid_duration", "Lease duration must be 30–86400 seconds", 422
        )
    if action == "claim":
        if token is not None and (
            not 32 <= len(token) <= 100
            or any(
                char
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for char in token
            )
        ):
            raise Conflict(
                "invalid_token", "Claim tokens must be 32–100 URL-safe characters", 422
            )
        if active(task):
            if (
                token
                and token_matches(task.lease_token, token)
                and task.lease_owner == owner
            ):
                # Recover a lost response without extending or changing the lease.
                return
            raise Conflict("task_locked", f"Task is claimed by {task.lease_owner}")
        if not owner or not owner.strip() or len(owner) > 100:
            raise Conflict(
                "invalid_owner", "An owner of 1–100 characters is required", 422
            )
        task.lease_owner = owner
        task.lease_token = token or secrets.token_urlsafe(32)
        task.lease_id = secrets.token_hex(16)
    elif not active(task) or not token_matches(task.lease_token, token):
        raise Conflict("invalid_lease", "Lease expired or token does not match")

    task.lease_expires_at = time.time() + seconds
    if action == "release":
        task.lease_owner = None
        task.lease_token = None
        task.lease_id = None
        task.lease_expires_at = None
