"""add notifications table

Revision ID: 38e071b5103e
Revises: db2494d820f6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "38e071b5103e"
down_revision: Union[str, Sequence[str], None] = "db2494d820f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_notifications_id", "notifications", ["id"], unique=False)
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_id", table_name="notifications")
    op.drop_table("notifications")
