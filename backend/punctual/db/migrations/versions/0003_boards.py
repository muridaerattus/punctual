"""Separate boards and durable, independently numbered ticket keys."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "boards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("prefix", sa.String(8), nullable=False, unique=True),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "length(prefix) BETWEEN 1 AND 8 AND prefix NOT GLOB '*[^A-Z]*'",
            name="board_prefix",
        ),
        sa.CheckConstraint("next_number > 0", name="board_sequence"),
    )
    # Preserve even deleted IDs: neither numeric IDs nor old PUN keys are reused.
    connection = op.get_bind()
    high_water = connection.scalar(sa.text("SELECT coalesce(max(id), 0) FROM tasks"))
    if connection.scalar(
        sa.text("SELECT count(*) FROM sqlite_master WHERE name = 'sqlite_sequence'")
    ):
        high_water = max(
            high_water,
            connection.scalar(
                sa.text(
                    "SELECT coalesce(max(seq), 0) FROM sqlite_sequence WHERE name = 'tasks'"
                )
            ),
        )
    connection.execute(
        sa.text("INSERT INTO boards VALUES (1, 'Default', 'PUN', :next)"),
        {"next": high_water + 1},
    )
    op.add_column("tasks", sa.Column("board_id", sa.Integer()))
    op.add_column("tasks", sa.Column("number", sa.Integer()))
    op.execute("UPDATE tasks SET board_id = 1, number = id")
    # SQLite's self-referencing RESTRICT FK prevents batch recreation with children.
    # Keep relationships and the AUTOINCREMENT high-water mark inside this transaction.
    op.execute(
        "CREATE TEMP TABLE board_migration_parents AS SELECT id, parent_id FROM tasks WHERE parent_id IS NOT NULL"
    )
    op.execute("UPDATE tasks SET parent_id = NULL")
    with op.batch_alter_table(
        "tasks", recreate="always", table_kwargs={"sqlite_autoincrement": True}
    ) as batch:
        batch.alter_column("board_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("number", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "task_board", "boards", ["board_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_unique_constraint("task_board_number", ["board_id", "number"])
        batch.create_check_constraint("task_number", "number > 0")
    op.execute(
        "UPDATE tasks SET parent_id = (SELECT parent_id FROM board_migration_parents WHERE id = tasks.id)"
    )
    op.execute("DROP TABLE board_migration_parents")
    op.execute(
        "UPDATE sqlite_sequence SET seq = (SELECT next_number - 1 FROM boards WHERE id = 1) WHERE name = 'tasks'"
    )


def downgrade():
    # Prefixes and independent sequences cannot be represented by the old schema.
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM boards WHERE id != 1")):
        raise RuntimeError("Cannot downgrade a database containing additional boards")
    high_water = op.get_bind().scalar(
        sa.text(
            "SELECT coalesce(max(seq), 0) FROM sqlite_sequence WHERE name = 'tasks'"
        )
    )
    op.execute(
        "CREATE TEMP TABLE board_migration_parents AS SELECT id, parent_id FROM tasks WHERE parent_id IS NOT NULL"
    )
    op.execute("UPDATE tasks SET parent_id = NULL")
    with op.batch_alter_table(
        "tasks", recreate="always", table_kwargs={"sqlite_autoincrement": True}
    ) as batch:
        batch.drop_constraint("task_board", type_="foreignkey")
        batch.drop_constraint("task_board_number", type_="unique")
        batch.drop_constraint("task_number", type_="check")
        batch.drop_column("board_id")
        batch.drop_column("number")
    op.execute(
        "UPDATE tasks SET parent_id = (SELECT parent_id FROM board_migration_parents WHERE id = tasks.id)"
    )
    op.execute("DROP TABLE board_migration_parents")
    op.get_bind().execute(
        sa.text("UPDATE sqlite_sequence SET seq = :seq WHERE name = 'tasks'"),
        {"seq": high_water},
    )
    op.drop_table("boards")
