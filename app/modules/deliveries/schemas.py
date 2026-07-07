from datetime import datetime
from pydantic import BaseModel, Field

from app.modules.deliveries.models import DeliveryStatus


class DeliveryCreate(BaseModel):
    order_id: int
    driver_id: int | None = None
    scheduled_at: datetime | None = None
    delivery_address: str | None = None
    delivery_notes: str | None = None


class AssignDriverRequest(BaseModel):
    driver_id: int


class UpdateDeliveryStatus(BaseModel):
    status: DeliveryStatus
    failure_reason: str | None = None


class UpdateDriverLocation(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class DeliveryResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    driver_id: int | None
    status: DeliveryStatus
    delivery_address: str
    delivery_notes: str | None
    scheduled_at: datetime | None
    picked_up_at: datetime | None
    delivered_at: datetime | None
    current_latitude: float | None
    current_longitude: float | None
    failure_reason: str | None
    created_at: datetime

    class Config:
        from_attributes = True