from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, Float, Integer, String
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


class MealPlan(Base):
    __tablename__ = "meal_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    name_en: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    name_ar: Mapped[str | None] = mapped_column(String(150), nullable=True)

    description_en: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description_ar: Mapped[str | None] = mapped_column(String(500), nullable=True)

    plan_type: Mapped[PlanType] = mapped_column(SqlEnum(PlanType), nullable=False)
    goal: Mapped[PlanGoal | None] = mapped_column(SqlEnum(PlanGoal), nullable=True)

    price: Mapped[float] = mapped_column(Float, nullable=False)

    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    meals_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    total_meals: Mapped[int] = mapped_column(Integer, nullable=False)

    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )