from datetime import datetime
from pydantic import BaseModel

from app.modules.subscriptions.models import PaymentStatus, SubscriptionStatus


class SubscriptionCreate(BaseModel):
    plan_id: int
    notes: str | None = None


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    plan_id: int
    status: SubscriptionStatus
    payment_status: PaymentStatus
    amount: float
    start_date: datetime | None
    end_date: datetime | None
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUpdateSubscription(BaseModel):
    status: SubscriptionStatus | None = None
    payment_status: PaymentStatus | None = None
    notes: str | None = None