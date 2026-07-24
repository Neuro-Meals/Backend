from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.modules.orders.models import OrderStatus


class ChefCustomerResponse(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    allergies: list[str] = Field(default_factory=list)
    dietary_preference: str | None = None


class ChefDriverResponse(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None


class ChefMealCategoryResponse(BaseModel):
    id: int
    name_en: str | None = None
    name_ar: str | None = None


class ChefDeliverySnapshotResponse(BaseModel):
    delivery_preference_id: int
    place_type: str | None = None
    place_name: str | None = None
    city: str | None = None
    area: str | None = None
    address: str
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None


class ChefOrderItemResponse(BaseModel):
    meal_assignment_item_id: int | None = None
    meal_id: int | None = None
    meal_name: str | None = None
    meal_name_ar: str | None = None
    description: str | None = None
    quantity: int = 1
    unit_price: float = 0
    line_total: float = 0
    calories: float | int | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None
    ingredients: list = Field(default_factory=list)
    allergens: list = Field(default_factory=list)
    diet_tags: list = Field(default_factory=list)
    image_url: str | None = None
    notes: str | None = None
    assignment_notes: str | None = None


class ChefOrderResponse(BaseModel):
    id: int
    order_number: str
    status: OrderStatus

    user_id: int
    subscription_id: int | None = None
    plan_id: int | None = None
    meal_assignment_id: int
    meal_category_id: int
    driver_id: int
    delivery_preference_id: int

    delivery_date: date
    delivery_time: time
    total_amount: float

    delivery_place_type: str | None = None
    delivery_place_name: str | None = None
    delivery_city: str | None = None
    delivery_area: str | None = None
    delivery_address: str
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None
    delivery_notes: str | None = None

    items: list[ChefOrderItemResponse] = Field(
        default_factory=list
    )

    confirmed_at: datetime | None = None
    preparation_started_at: datetime | None = None
    ready_at: datetime | None = None
    out_for_delivery_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None

    created_at: datetime
    updated_at: datetime

    customer: ChefCustomerResponse | None = None
    driver: ChefDriverResponse | None = None
    meal_category: ChefMealCategoryResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class ChefStatusResponse(BaseModel):
    message: str
    order: ChefOrderResponse


class ChefDashboardResponse(BaseModel):
    date: date
    total_orders: int
    scheduled_orders: int
    pending_orders: int
    confirmed_orders: int
    preparing_orders: int
    ready_for_delivery_orders: int
    out_for_delivery_orders: int
    delivered_orders: int
    cancelled_orders: int
    total_meal_items: int
    total_meal_quantity: int


class ChefMealSummaryItem(BaseModel):
    meal_id: int | None = None
    meal_name: str
    quantity: int


class ChefMealSummaryResponse(BaseModel):
    date: date
    total_orders: int
    total_meals: int
    meals: list[ChefMealSummaryItem] = Field(
        default_factory=list
    )


class ChefAllergySummaryItem(BaseModel):
    allergy: str
    customer_count: int
    order_count: int


class ChefAllergyCustomerResponse(BaseModel):
    user_id: int
    full_name: str
    phone: str | None = None
    allergies: list[str] = Field(default_factory=list)
    order_ids: list[int] = Field(default_factory=list)


class ChefAllergySummaryResponse(BaseModel):
    date: date
    total_orders: int
    customers_with_allergies: int
    allergies: list[ChefAllergySummaryItem] = Field(
        default_factory=list
    )
    customers: list[ChefAllergyCustomerResponse] = Field(
        default_factory=list
    )


class ChefBulkStatusRequest(BaseModel):
    order_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=200,
    )


class ChefBulkStatusItemResponse(BaseModel):
    order_id: int
    order_number: str
    status: OrderStatus


class ChefBulkStatusErrorResponse(BaseModel):
    order_id: int
    reason: str


class ChefBulkStatusResponse(BaseModel):
    message: str
    requested_orders: int
    updated_orders: int
    failed_orders: int
    orders: list[ChefBulkStatusItemResponse] = Field(
        default_factory=list
    )
    failures: list[ChefBulkStatusErrorResponse] = Field(
        default_factory=list
    )