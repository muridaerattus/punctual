from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from punctual.db.models import Base
from punctual.tasks.schemas import TaskInput
from punctual.tasks.service import TaskService
from punctual.tasks.write_schemas import CompleteTaskInput


def test_migrations_match_models_and_preserve_data(tmp_path):
    store = TaskService(str(tmp_path / "migrated.db"))
    task = store.create(TaskInput(title="Survives migration"))
    lease = store.lease(task["id"], "claim", owner="agent")
    with store.database.engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == "0004"
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


def test_workflow_completes_migrated_legacy_lease(tmp_path):
    path = tmp_path / "legacy-workflow.db"
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
            VALUES (1, 'Legacy', '', 'In Progress', 3, 1, 1,
                'agent', 'old-token', 9999999999)
        """)
        )
    engine.dispose()
    store = TaskService(str(path))
    try:
        data = CompleteTaskInput(
            revision=3, lease_token="old-token", request_id="r" * 32
        )
        result = store.complete_task("PUN-1", data)
        assert result["task"]["status"] == "Complete"
        assert result["task"]["revision"] == 4
        assert result["task"]["lease_owner"] is None
        assert store.complete_task("PUN-1", data)["replayed"] is True
    finally:
        store.database.engine.dispose()


def test_board_migration_preserves_children_leases_and_deleted_high_water(tmp_path):
    path = tmp_path / "boards-migration.db"
    engine = create_engine(f"sqlite:///{path}")
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[1] / "punctual/db/migrations")
    )
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
        connection.execute(
            text("""
            INSERT INTO tasks (id, title, description, status, parent_id, revision,
                created_at, updated_at, lease_owner, lease_token, lease_expires_at, lease_id)
            VALUES (5, 'Parent', 'Preserved', 'In Progress', NULL, 7, 1, 2,
                'agent', 'saved-token', 9999999999, '0123456789abcdef0123456789abcdef'),
                (9, 'Child', '', 'To Do', 5, 3, 3, 4, NULL, NULL, NULL, NULL),
                (99, 'Deleted', '', 'Complete', NULL, 1, 1, 1, NULL, NULL, NULL, NULL)
        """)
        )
        connection.execute(text("DELETE FROM tasks WHERE id = 99"))
    engine.dispose()
    # Startup uses foreign_keys=ON, unlike a plain Alembic connection.
    store = TaskService(str(path))
    try:
        parent, child = store.get(5), store.get(9)
        assert (parent["key"], child["key"], child["parent_key"]) == (
            "PUN-5",
            "PUN-9",
            "PUN-5",
        )
        assert (
            parent["revision"],
            parent["status"],
            parent["description"],
            parent["updated_at"],
        ) == (7, "In Progress", "Preserved", 2)
        assert parent["lease_id"] == "0123456789abcdef0123456789abcdef"
        store.lease(5, "release", token="saved-token")
        task = store.create(TaskInput(title="After migration"))
        assert (task["id"], task["key"]) == (100, "PUN-100")
        with store.database.engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    finally:
        store.database.engine.dispose()
