from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.subscriptions.models import (
    PaymentStatus,
    SubscriptionStatus,
)


class SubscriptionCreate(BaseModel):
    plan_id: int
    notes: str | None = None


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    plan_id: int
    pending_plan_id: int | None = None

    status: SubscriptionStatus
    payment_status: PaymentStatus

    amount: float

    start_date: datetime | None = None
    end_date: datetime | None = None
    paused_at: datetime | None = None

    total_paused_seconds: int = 0
    pause_count: int = 0

    plan_change_effective_at: datetime | None = None
    cancelled_at: datetime | None = None

    auto_renew: bool = False
    notes: str | None = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUpdateSubscription(BaseModel):
    status: SubscriptionStatus | None = None
    payment_status: PaymentStatus | None = None
    notes: str | None = None
    auto_renew: bool | None = None


class PauseSubscriptionRequest(BaseModel):
    reason: str | None = Field(
        default=None,
        max_length=500,
    )


class PauseHistoryResponse(BaseModel):
    id: int
    subscription_id: int
    user_id: int
    reason: str | None = None
    paused_at: datetime
    resumed_at: datetime | None = None
    duration_seconds: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PauseSubscriptionResponse(BaseModel):
    message: str
    subscription_id: int
    status: str
    paused_at: datetime
    pause_count: int


class ResumeSubscriptionResponse(BaseModel):
    message: str
    subscription_id: int
    status: str
    paused_seconds: int
    paused_days: float
    old_end_date: datetime | None = None
    new_end_date: datetime | None = None
    total_paused_seconds: int


class ChangePlanRequest(BaseModel):
    new_plan_id: int


class PlanChangeResponse(BaseModel):
    id: int
    subscription_id: int
    user_id: int

    old_plan_id: int
    new_plan_id: int

    change_type: str
    status: str

    old_amount: float
    new_amount: float
    amount_difference: float

    effective_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChangePlanResult(BaseModel):
    message: str
    plan_change: PlanChangeResponse
    requires_payment: bool
    amount_due: float
    
    
class CustomerMealCategoryResponse(BaseModel):
    id: int
    name_en: str
    name_ar: str | None = None


class CustomerMealResponse(BaseModel):
    id: int
    name_en: str
    name_ar: str | None = None
    description_en: str | None = None
    description_ar: str | None = None

    quantity: int

    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None

    ingredients: list[str] | None = None
    allergens: list[str] | None = None

    image_url: str | None = None


class CustomerDayCategoryResponse(BaseModel):
    category: CustomerMealCategoryResponse
    meals: list[CustomerMealResponse]


class CustomerDayMenuResponse(BaseModel):
    day_of_week: str
    categories: list[CustomerDayCategoryResponse]


class CustomerCurrentDayMenuResponse(BaseModel):
    day_of_week: str
    date: str
    categories: list[CustomerDayCategoryResponse]


class CustomerPlanDetailsResponse(BaseModel):
    id: int
    name_en: str
    name_ar: str | None = None

    description_en: str | None = None
    description_ar: str | None = None

    plan_type: str | None = None
    goal: str | None = None

    price: float
    duration_days: int
    meals_per_day: int
    total_meals: int

    image_url: str | None = None


class CustomerSubscriptionDetailsResponse(BaseModel):
    id: int
    status: SubscriptionStatus
    payment_status: PaymentStatus

    amount: float

    start_date: datetime | None = None
    end_date: datetime | None = None
    paused_at: datetime | None = None
    cancelled_at: datetime | None = None

    notes: str | None = None


class MyCurrentSubscriptionDetailsResponse(BaseModel):
    subscription: CustomerSubscriptionDetailsResponse
    plan: CustomerPlanDetailsResponse

    today: CustomerCurrentDayMenuResponse
    tomorrow: CustomerCurrentDayMenuResponse

    weekly_menu: list[CustomerDayMenuResponse]

    model_config = ConfigDict(from_attributes=True)    