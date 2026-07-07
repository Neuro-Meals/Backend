from datetime import datetime
from pydantic import BaseModel

from app.modules.orders.models import OrderStatus


class OrderFromSubscriptionCreate(BaseModel):
    subscription_id: int
    delivery_address: str | None = None
    delivery_notes: str | None = None


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderResponse(BaseModel):
    id: int
    user_id: int
    subscription_id: int | None
    plan_id: int | None
    order_number: str
    status: OrderStatus
    total_amount: float
    delivery_date: datetime | None
    delivery_address: str | None
    delivery_notes: str | None
    items: list[dict] | None
    created_at: datetime

    class Config:
        from_attributes = True