from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.modules.deliveries.models import DeliveryStatus
from app.modules.orders.models import OrderStatus


class UpdateDriverLocation(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class FailDeliveryRequest(BaseModel):
    reason: str = Field(
        ...,
        min_length=3,
        max_length=500,
    )


class DeliveryCustomerResponse(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None


class DeliveryDriverResponse(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None


class DeliveryOrderResponse(BaseModel):
    id: int
    order_number: str
    status: OrderStatus

    user_id: int
    driver_id: int
    meal_category_id: int

    delivery_date: date
    delivery_time: time
    delivery_address: str
    delivery_notes: str | None = None

    total_amount: float
    items: list[dict] = Field(default_factory=list)


class DeliveryResponse(BaseModel):
    id: int
    order_id: int
    status: DeliveryStatus

    ready_for_pickup_at: datetime | None = None
    picked_up_at: datetime | None = None
    out_for_delivery_at: datetime | None = None
    delivered_at: datetime | None = None
    failed_at: datetime | None = None
    cancelled_at: datetime | None = None

    current_latitude: float | None = None
    current_longitude: float | None = None
    failure_reason: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DriverDeliveryResponse(DeliveryResponse):
    order: DeliveryOrderResponse
    customer: DeliveryCustomerResponse | None = None
    driver: DeliveryDriverResponse | None = None


class DriverDashboardSummary(BaseModel):
    date: date
    total_assigned: int
    ready_for_pickup: int
    picked_up: int
    out_for_delivery: int
    delivered: int
    failed: int


class DriverDashboardResponse(BaseModel):
    driver: DeliveryDriverResponse
    summary: DriverDashboardSummary
    current_delivery: DriverDeliveryResponse | None = None
    next_delivery: DriverDeliveryResponse | None = None


class DeliveryStatusResponse(BaseModel):
    message: str
    delivery: DriverDeliveryResponse