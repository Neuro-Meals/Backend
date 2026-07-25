from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MealSelection(Base):
    __tablename__ = "meal_selections"

    id = ...

    user_id = ...
    subscription_id = ...
    plan_id = ...
    meal_id = ...

    day_number = ...
    meal_time = ...

    is_skipped = ...
    skip_reason = ...

    created_at = ...
    updated_at = ...

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