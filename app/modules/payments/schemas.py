from datetime import datetime
from pydantic import BaseModel

from app.modules.payments.models import PaymentProvider, PaymentRecordStatus


class CreateCheckoutRequest(BaseModel):
    subscription_id: int


class CheckoutResponse(BaseModel):
    payment_id: int
    checkout_url: str
    stripe_checkout_session_id: str


class PaymentResponse(BaseModel):
    id: int
    user_id: int
    subscription_id: int
    provider: PaymentProvider
    status: PaymentRecordStatus
    amount: float
    currency: str
    checkout_url: str | None
    stripe_checkout_session_id: str | None
    stripe_payment_intent_id: str | None
    paid_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True