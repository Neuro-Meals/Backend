from datetime import date

from pydantic import BaseModel


class GeneratedOrderSummary(BaseModel):
    order_id: int
    order_number: str
    subscription_id: int
    user_id: int
    plan_id: int
    status: str
    meal_items: int


class SkippedSubscriptionSummary(BaseModel):
    subscription_id: int
    user_id: int | None = None
    reason: str


class AutomaticOrderGenerationResponse(BaseModel):
    target_date: date
    weekday: str

    subscriptions_checked: int
    orders_created: int
    already_existing: int

    skipped_no_menu: int
    skipped_invalid_subscription: int
    skipped_user_not_found: int
    skipped_address_missing: int

    created_orders: list[
        GeneratedOrderSummary
    ]

    skipped: list[
        SkippedSubscriptionSummary
    ]