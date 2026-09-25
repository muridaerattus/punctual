"""Public lease identities and durable forced-release records."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("lease_id", sa.String(32)))
    op.execute(
        "UPDATE tasks SET lease_id = lower(hex(randomblob(16))) "
        "WHERE lease_token IS NOT NULL"
    )
    op.create_table(
        "lease_releases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("lease_id", sa.String(32), nullable=False),
        sa.Column("lease_owner", sa.String(100), nullable=False),
        sa.Column("released_at", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
    )
    op.create_index("ix_lease_releases_task_id", "lease_releases", ["task_id"])


def downgrade():
    op.drop_table("lease_releases")
    op.drop_column("tasks", "lease_id")
