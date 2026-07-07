from datetime import datetime
from pydantic import BaseModel, Field


class MealSelectionCreate(BaseModel):
    subscription_id: int
    meal_id: int
    day_number: int = Field(..., ge=1)
    meal_time: str = Field(..., min_length=2, max_length=50)


class MealSelectionUpdate(BaseModel):
    meal_id: int | None = None
    is_skipped: bool | None = None
    skip_reason: str | None = None


class MealSelectionResponse(BaseModel):
    id: int
    user_id: int
    subscription_id: int
    plan_id: int
    meal_id: int
    day_number: int
    meal_time: str
    is_skipped: bool
    skip_reason: str | None
    created_at: datetime

    class Config:
        from_attributes = True