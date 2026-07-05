from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.plans.models import PlanGoal, PlanType


class MealPlanCreate(BaseModel):
    name_en: str = Field(..., min_length=2, max_length=150)
    name_ar: str | None = None

    description_en: str | None = None
    description_ar: str | None = None

    plan_type: PlanType
    goal: PlanGoal | None = None

    price: float = Field(..., ge=0)

    duration_days: int = Field(..., ge=1)
    meals_per_day: int = Field(..., ge=1)
    total_meals: int = Field(..., ge=1)

    image_url: str | None = None
    is_active: bool = True


class MealPlanUpdate(BaseModel):
    name_en: str | None = Field(None, min_length=2, max_length=150)
    name_ar: str | None = None

    description_en: str | None = None
    description_ar: str | None = None

    plan_type: PlanType | None = None
    goal: PlanGoal | None = None

    price: float | None = Field(None, ge=0)

    duration_days: int | None = Field(None, ge=1)
    meals_per_day: int | None = Field(None, ge=1)
    total_meals: int | None = Field(None, ge=1)

    image_url: str | None = None
    is_active: bool | None = None


class MealPlanResponse(BaseModel):
    id: int

    name_en: str
    name_ar: str | None

    description_en: str | None
    description_ar: str | None

    plan_type: PlanType
    goal: PlanGoal | None

    price: float

    duration_days: int
    meals_per_day: int
    total_meals: int

    image_url: str | None
    is_active: bool

    created_at: datetime

    class Config:
        from_attributes = True