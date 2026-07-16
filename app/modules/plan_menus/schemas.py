from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.plan_menus.models import WeekDay


class PlanMenuItemCreate(BaseModel):
    plan_id: int = Field(..., ge=1)
    meal_id: int = Field(..., ge=1)
    category_id: int = Field(..., ge=1)

    day_of_week: WeekDay

    quantity: int = Field(
        default=1,
        ge=1,
        le=100,
    )

    sort_order: int = Field(
        default=0,
        ge=0,
    )


class PlanMenuItemUpdate(BaseModel):
    meal_id: int | None = Field(
        default=None,
        ge=1,
    )

    category_id: int | None = Field(
        default=None,
        ge=1,
    )

    day_of_week: WeekDay | None = None

    quantity: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )

    sort_order: int | None = Field(
        default=None,
        ge=0,
    )

    is_active: bool | None = None


class PlanMenuMealResponse(BaseModel):
    id: int
    name_en: str
    name_ar: str | None = None
    image_url: str | None = None

    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None

    ingredients: list[str] | None = None
    allergens: list[str] | None = None


class PlanMenuCategoryResponse(BaseModel):
    id: int
    name_en: str
    name_ar: str | None = None


class PlanMenuItemResponse(BaseModel):
    id: int
    plan_id: int
    meal_id: int
    category_id: int

    day_of_week: WeekDay
    quantity: int
    sort_order: int
    is_active: bool

    meal: PlanMenuMealResponse | None = None
    category: PlanMenuCategoryResponse | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanDayMenuResponse(BaseModel):
    day_of_week: WeekDay
    categories: list[dict]


class PlanWeeklyMenuResponse(BaseModel):
    plan_id: int
    plan_name: str
    days: list[PlanDayMenuResponse]