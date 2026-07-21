from datetime import datetime
from enum import Enum
from app.modules.plans.models import MealTime
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

class WeekDay(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class PlanMenuItem(Base):
    __tablename__ = "plan_menu_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
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

    category_id: Mapped[int] = mapped_column(
        ForeignKey(
            "meal_categories.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    day_of_week: Mapped[WeekDay] = mapped_column(
    SqlEnum(
        WeekDay,
        name="weekday",
    ),
    nullable=False,
    index=True,
)

    meal_time: Mapped[MealTime] = mapped_column(
    SqlEnum(
        MealTime,
        name="planmenumealtime",
    ),
    nullable=False,
    default=MealTime.LUNCH,
    index=True,
)

    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
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
        "plan_id",
        "day_of_week",
        "meal_time",
        "category_id",
        "meal_id",
        name="unique_plan_day_time_category_meal",
    ),
)