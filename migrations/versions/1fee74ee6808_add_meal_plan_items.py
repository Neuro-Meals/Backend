"""add meal plan items

Revision ID: 1fee74ee6808
Revises: 38e071b5103e
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1fee74ee6808"
down_revision: Union[str, Sequence[str], None] = "38e071b5103e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meal_plan_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("meal_id", sa.Integer(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("meal_time", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plan_id",
            "meal_id",
            "day_number",
            "meal_time",
            name="unique_plan_meal_day_time",
        ),
    )

    op.create_index("ix_meal_plan_items_id", "meal_plan_items", ["id"], unique=False)
    op.create_index("ix_meal_plan_items_plan_id", "meal_plan_items", ["plan_id"], unique=False)
    op.create_index("ix_meal_plan_items_meal_id", "meal_plan_items", ["meal_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_meal_plan_items_meal_id", table_name="meal_plan_items")
    op.drop_index("ix_meal_plan_items_plan_id", table_name="meal_plan_items")
    op.drop_index("ix_meal_plan_items_id", table_name="meal_plan_items")
    op.drop_table("meal_plan_items")
