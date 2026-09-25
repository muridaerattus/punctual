from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from punctual.db.models import Base
from punctual.tasks.schemas import TaskInput
from punctual.tasks.service import TaskService


def test_migrations_match_models_and_preserve_data(tmp_path):
    store = TaskService(str(tmp_path / "migrated.db"))
    task = store.create(TaskInput(title="Survives migration"))
    lease = store.lease(task["id"], "claim", owner="agent")
    with store.database.engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == "0002"
        assert compare_metadata(context, Base.metadata) == []

    restarted = TaskService(store.path)
    assert restarted.get(task["id"])["title"] == task["title"]
    assert restarted.get(task["id"])["lease_owner"] == "agent"
    restarted.lease(task["id"], "release", token=lease["lease_token"])


def test_alembic_upgrade_downgrade(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'roundtrip.db'}")
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[1] / "punctual/db/migrations")
    )
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert inspect(connection).has_table("tasks")
        command.downgrade(config, "base")
        assert not inspect(connection).has_table("tasks")
        command.upgrade(config, "head")
        assert inspect(connection).has_table("tasks")


def test_upgrade_preserves_existing_active_lease(tmp_path):
    path = tmp_path / "existing.db"
    engine = create_engine(f"sqlite:///{path}")
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[1] / "punctual/db/migrations")
    )
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
        connection.execute(
            text("""
            INSERT INTO tasks (id, title, description, status, revision, created_at,
                updated_at, lease_owner, lease_token, lease_expires_at)
            VALUES (1, 'Existing', '', 'To Do', 1, 1, 1, 'agent', 'old-token', 9999999999)
        """)
        )
    engine.dispose()
    store = TaskService(str(path))
    try:
        migrated = store.get(1)
        assert migrated["lease_owner"] == "agent"
        assert len(migrated["lease_id"]) == 32
        store.lease(1, "release", token="old-token")
    finally:
        store.database.engine.dispose()
