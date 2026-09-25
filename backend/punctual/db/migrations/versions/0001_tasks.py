"""Create the task board, including durable task leases."""

import sqlalchemy as sa
from alembic import context, op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Adopt the compatible pre-Alembic prototype without discarding its data.
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if inspector.has_table("tasks"):
            required = {
                "id",
                "title",
                "description",
                "status",
                "assignee",
                "parent_id",
                "revision",
                "created_at",
                "updated_at",
                "lease_owner",
                "lease_token",
                "lease_expires_at",
            }
            if {
                column["name"] for column in inspector.get_columns("tasks")
            } != required:
                raise RuntimeError("Cannot adopt an incompatible existing tasks table")
            return
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("assignee", sa.String(100)),
        sa.Column(
            "parent_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="RESTRICT")
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
        sa.Column("lease_owner", sa.String(100)),
        sa.Column("lease_token", sa.String(100)),
        sa.Column("lease_expires_at", sa.Float()),
        sa.CheckConstraint(
            "status IN ('To Do', 'In Progress', 'Complete')", name="task_status"
        ),
        sqlite_autoincrement=True,
    )
    op.create_index("tasks_parent", "tasks", ["parent_id"])


def downgrade():
    op.drop_index("tasks_parent", table_name="tasks")
    op.drop_table("tasks")
