from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.deliveries.models import DeliveryStatus


class DeliveryCreate(BaseModel):
    order_id: int
    driver_id: int | None = None
    delivery_address: str | None = None
    delivery_notes: str | None = None
    scheduled_at: datetime | None = None


class AssignDriverRequest(BaseModel):
    driver_id: int


class UpdateDeliveryStatus(BaseModel):
    status: DeliveryStatus
    failure_reason: str | None = None


class UpdateDriverLocation(BaseModel):
    latitude: float
    longitude: float


class DeliveryResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    driver_id: int | None = None

    status: DeliveryStatus

    delivery_address: str
    delivery_notes: str | None = None

    scheduled_at: datetime | None = None
    picked_up_at: datetime | None = None
    delivered_at: datetime | None = None

    current_latitude: float | None = None
    current_longitude: float | None = None

    failure_reason: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeliveryCustomerResponse(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    address: str | None = None


class DeliveryDriverResponse(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None


class DeliveryOrderResponse(BaseModel):
    id: int
    order_number: str | None = None
    status: str | None = None
    total_amount: float | None = None
    delivery_date: datetime | None = None
    items: list[dict] | None = None


class DriverDeliveryResponse(BaseModel):
    id: int
    status: DeliveryStatus

    delivery_address: str
    delivery_notes: str | None = None

    scheduled_at: datetime | None = None
    picked_up_at: datetime | None = None
    delivered_at: datetime | None = None

    current_latitude: float | None = None
    current_longitude: float | None = None

    failure_reason: str | None = None

    created_at: datetime
    updated_at: datetime

    customer: DeliveryCustomerResponse | None = None
    driver: DeliveryDriverResponse | None = None
    order: DeliveryOrderResponse | None = None

    model_config = ConfigDict(from_attributes=True)