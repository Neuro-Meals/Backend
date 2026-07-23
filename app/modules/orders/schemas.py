from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.orders.models import (
    OrderSource,
    OrderStatus,
)


class OrderItemResponse(BaseModel):
    assignment_id: int | None = None

    meal_id: int
    meal_category_id: int | None = None

    meal_name: str
    meal_name_ar: str | None = None

    category_name: str | None = None
    category_name_ar: str | None = None

    quantity: int = 1

    unit_price: float = 0
    line_total: float = 0

    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None

    ingredients: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)

    image_url: str | None = None


class OrderFromSubscriptionCreate(BaseModel):
    subscription_id: int
    delivery_date: datetime

    delivery_preference_id: int | None = None

    delivery_address: str | None = Field(
        default=None,
        max_length=500,
    )

    delivery_notes: str | None = Field(
        default=None,
        max_length=1000,
    )


class ManualOrderCreate(BaseModel):
    user_id: int

    subscription_id: int | None = None
    plan_id: int | None = None

    delivery_date: datetime

    delivery_preference_id: int | None = None

    delivery_address: str | None = Field(
        default=None,
        max_length=500,
    )

    delivery_notes: str | None = Field(
        default=None,
        max_length=1000,
    )

    items: list[OrderItemResponse] = Field(
        default_factory=list,
    )


class OrderStatusUpdate(BaseModel):
    status: OrderStatus

    cancellation_reason: str | None = Field(
        default=None,
        max_length=500,
    )


class OrderDeliveryUpdate(BaseModel):
    delivery_date: datetime | None = None
    delivery_preference_id: int | None = None

    delivery_place_type: str | None = None
    delivery_place_name: str | None = None
    delivery_city: str | None = None
    delivery_area: str | None = None

    delivery_address: str | None = Field(
        default=None,
        max_length=500,
    )

    delivery_latitude: float | None = None
    delivery_longitude: float | None = None

    delivery_notes: str | None = Field(
        default=None,
        max_length=1000,
    )


class OrderResponse(BaseModel):
    id: int

    user_id: int
    subscription_id: int | None
    plan_id: int | None

    order_number: str

    source: OrderSource
    status: OrderStatus

    total_amount: float

    delivery_date: datetime | None
    delivery_preference_id: int | None

    delivery_place_type: str | None
    delivery_place_name: str | None
    delivery_city: str | None
    delivery_area: str | None

    delivery_address: str | None
    delivery_latitude: float | None
    delivery_longitude: float | None

    delivery_notes: str | None

    items: list[dict]

    confirmed_at: datetime | None
    preparation_started_at: datetime | None
    ready_at: datetime | None
    out_for_delivery_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None

    cancellation_reason: str | None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    data: list[OrderResponse]

    total: int
    page: int
    limit: int
    pages: int


class OrderActionResponse(BaseModel):
    success: bool
    message: str
    data: OrderResponse | None = None