from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    Float,
    Integer,
    String,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class PlanType(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"
    FAMILY = "family"
    CORPORATE = "corporate"


class PlanGoal(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    MAINTENANCE = "maintenance"
    HEALTHY_LIFESTYLE = "healthy_lifestyle"


class DeliveryType(str, Enum):
    INDIVIDUAL = "individual"
    BULK = "bulk"


class DeliveryTemperature(str, Enum):
    HOT = "hot"
    COLD = "cold"


class MealTime(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class MealPlan(Base):
    __tablename__ = "meal_plans"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name_en: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    name_ar: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    description_en: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    description_ar: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    plan_type: Mapped[PlanType] = mapped_column(
        SqlEnum(
            PlanType,
            name="plantype",
        ),
        nullable=False,
    )

    goal: Mapped[PlanGoal | None] = mapped_column(
        SqlEnum(
            PlanGoal,
            name="plangoal",
        ),
        nullable=True,
    )

    delivery_type: Mapped[DeliveryType] = mapped_column(
        SqlEnum(
            DeliveryType,
            name="deliverytype",
        ),
        nullable=False,
        default=DeliveryType.INDIVIDUAL,
    )

    delivery_temperature: Mapped[DeliveryTemperature] = mapped_column(
        SqlEnum(
            DeliveryTemperature,
            name="deliverytemperature",
        ),
        nullable=False,
        default=DeliveryTemperature.HOT,
    )

    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    duration_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    meals_per_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_meals: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
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


class MealPlanItem(Base):
    __tablename__ = "meal_plan_items"

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

    day_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    meal_time: Mapped[MealTime] = mapped_column(
        SqlEnum(
            MealTime,
            name="mealtime",
        ),
        nullable=False,
        default=MealTime.LUNCH,
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

    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "meal_id",
            "day_number",
            "meal_time",
            name="unique_plan_meal_day_time",
        ),
    )