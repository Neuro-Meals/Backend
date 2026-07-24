from datetime import date, time

from pydantic import BaseModel, Field


class GeneratedOrderSummary(BaseModel):
    """
    Summary of one order generated from one MealAssignment.
    """

    order_id: int
    order_number: str

    meal_assignment_id: int
    subscription_id: int | None = None
    user_id: int
    plan_id: int | None = None

    meal_category_id: int
    driver_id: int
    delivery_preference_id: int

    delivery_date: date
    delivery_time: time

    status: str

    meal_items: int
    total_quantity: int
    total_amount: float


class SkippedAssignmentSummary(BaseModel):
    """
    Explains why an individual MealAssignment did not produce
    an order.
    """

    meal_assignment_id: int
    subscription_id: int | None = None
    user_id: int
    meal_category_id: int

    reason_code: str
    reason: str


class AutomaticOrderGenerationResponse(BaseModel):
    """
    Response returned when orders are generated for a date.

    One MealAssignment creates one Order.
    """

    target_date: date

    assignments_checked: int

    orders_created: int
    already_existing: int

    skipped_inactive_assignment: int = 0
    skipped_invalid_subscription: int = 0
    skipped_no_meals: int = 0
    skipped_missing_customer: int = 0
    skipped_missing_driver: int = 0
    skipped_missing_delivery_preference: int = 0
    skipped_missing_delivery_location: int = 0
    skipped_missing_delivery_time: int = 0

    created_orders: list[GeneratedOrderSummary] = Field(
        default_factory=list,
    )

    existing_orders: list[GeneratedOrderSummary] = Field(
        default_factory=list,
    )

    skipped: list[SkippedAssignmentSummary] = Field(
        default_factory=list,
    )


class ConfirmedOrdersResponse(BaseModel):
    """
    Response returned when scheduled orders are confirmed.
    """

    target_date: date
    orders_confirmed: int

    order_ids: list[int] = Field(
        default_factory=list,
    )

    order_numbers: list[str] = Field(
        default_factory=list,
    )