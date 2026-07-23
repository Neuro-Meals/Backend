from datetime import date

from pydantic import BaseModel, Field


class GeneratedOrderSummary(BaseModel):
    order_id: int
    order_number: str

    subscription_id: int
    user_id: int
    plan_id: int | None = None

    status: str
    meal_items: int
    total_quantity: int

    delivery_locations: int


class SkippedSubscriptionSummary(BaseModel):
    subscription_id: int | None = None
    user_id: int | None = None

    reason: str


class AutomaticOrderGenerationResponse(BaseModel):
    target_date: date

    subscriptions_checked: int
    subscriptions_with_assignments: int

    orders_created: int
    already_existing: int

    skipped_no_assignments: int
    skipped_invalid_subscription: int
    skipped_user_not_found: int
    skipped_missing_delivery_location: int

    created_orders: list[GeneratedOrderSummary] = Field(
        default_factory=list,
    )

    skipped: list[SkippedSubscriptionSummary] = Field(
        default_factory=list,
    )