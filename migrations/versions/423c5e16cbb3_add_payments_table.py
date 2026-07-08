"""add payments table

Revision ID: 423c5e16cbb3
Revises: e07b3aa7e4e4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "423c5e16cbb3"
down_revision: Union[str, Sequence[str], None] = "e07b3aa7e4e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("checkout_url", sa.String(length=1000), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_payments_id", "payments", ["id"], unique=False)
    op.create_index("ix_payments_user_id", "payments", ["user_id"], unique=False)
    op.create_index("ix_payments_subscription_id", "payments", ["subscription_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payments_subscription_id", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_index("ix_payments_id", table_name="payments")
    op.drop_table("payments")
