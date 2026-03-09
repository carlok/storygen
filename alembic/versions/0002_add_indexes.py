"""Add performance indexes for daily-limit query and user email lookup

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite index for the daily-limit query in generate():
    #   WHERE user_id = ? AND created_at >= ?
    op.create_index(
        "ix_jobs_user_created_at",
        "jobs",
        ["user_id", "created_at"],
    )

    # Index for the email-based lookups in auth_callback() and promote_initial_admin()
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_jobs_user_created_at", table_name="jobs")
