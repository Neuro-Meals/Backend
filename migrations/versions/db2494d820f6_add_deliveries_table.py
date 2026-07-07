"""add deliveries table

Revision ID: db2494d820f6
Revises: f92adfe6d1d4
Create Date: 2026-07-07 21:36:09.459170
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "db2494d820f6"
down_revision: Union[str, Sequence[str], None] = "f92adfe6d1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    delivery_status_enum = sa.Enum(
        "PENDING",
        "ASSIGNED",
        "PICKED_UP",
        "OUT_FOR_DELIVERY",
        "DELIVERED",
        "FAILED",
        "CANCELLED",
        name="deliverystatus",
        create_type=False,
    )

    op.create_table(
        "deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=True),
        sa.Column("status", delivery_status_enum, nullable=False),
        sa.Column("delivery_address", sa.String(length=255), nullable=False),
        sa.Column("delivery_notes", sa.String(length=500), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("picked_up_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("current_latitude", sa.Float(), nullable=True),
        sa.Column("current_longitude", sa.Float(), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_deliveries_id", "deliveries", ["id"], unique=False)
    op.create_index("ix_deliveries_order_id", "deliveries", ["order_id"], unique=False)
    op.create_index("ix_deliveries_user_id", "deliveries", ["user_id"], unique=False)
    op.create_index("ix_deliveries_driver_id", "deliveries", ["driver_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_deliveries_driver_id", table_name="deliveries")
    op.drop_index("ix_deliveries_user_id", table_name="deliveries")
    op.drop_index("ix_deliveries_order_id", table_name="deliveries")
    op.drop_index("ix_deliveries_id", table_name="deliveries")
    op.drop_table("deliveries")



