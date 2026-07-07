"""add meal selections

Revision ID: e07b3aa7e4e4
Revises: 1fee74ee6808
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e07b3aa7e4e4"
down_revision: Union[str, Sequence[str], None] = "1fee74ee6808"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meal_selections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("meal_id", sa.Integer(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("meal_time", sa.String(length=50), nullable=False),
        sa.Column("is_skipped", sa.Boolean(), nullable=False),
        sa.Column("skip_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "subscription_id",
            "day_number",
            "meal_time",
            name="unique_user_subscription_day_meal_time",
        ),
    )

    op.create_index("ix_meal_selections_id", "meal_selections", ["id"], unique=False)
    op.create_index("ix_meal_selections_user_id", "meal_selections", ["user_id"], unique=False)
    op.create_index("ix_meal_selections_subscription_id", "meal_selections", ["subscription_id"], unique=False)
    op.create_index("ix_meal_selections_plan_id", "meal_selections", ["plan_id"], unique=False)
    op.create_index("ix_meal_selections_meal_id", "meal_selections", ["meal_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_meal_selections_meal_id", table_name="meal_selections")
    op.drop_index("ix_meal_selections_plan_id", table_name="meal_selections")
    op.drop_index("ix_meal_selections_subscription_id", table_name="meal_selections")
    op.drop_index("ix_meal_selections_user_id", table_name="meal_selections")
    op.drop_index("ix_meal_selections_id", table_name="meal_selections")
    op.drop_table("meal_selections")
