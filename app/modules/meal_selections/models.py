from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MealSelection(Base):
    __tablename__ = "meal_selections"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey(
            "subscriptions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    plan_id: Mapped[int] = mapped_column(
        ForeignKey(
            "meal_plans.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    meal_id: Mapped[int] = mapped_column(
        ForeignKey(
            "meals.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    day_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    meal_time: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    is_skipped: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    skip_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "subscription_id",
            "day_number",
            "meal_time",
            "meal_id",
            name="unique_user_subscription_day_meal_time",
        ),
    )