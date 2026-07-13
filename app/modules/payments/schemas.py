from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.payments.models import (
    PaymentProvider,
    PaymentRecordStatus,
)


class CreateCheckoutRequest(BaseModel):
    subscription_id: int


class CreatePlanChangeCheckoutRequest(BaseModel):
    plan_change_id: int


class CheckoutResponse(BaseModel):
    payment_id: int
    checkout_url: str
    tap_charge_id: str
    status: str


class PaymentResponse(BaseModel):
    id: int
    user_id: int
    subscription_id: int
    plan_change_id: int | None = None

    provider: PaymentProvider
    status: PaymentRecordStatus

    amount: float
    currency: str

    checkout_url: str | None = None

    tap_charge_id: str | None = None
    tap_payment_reference: str | None = None
    tap_gateway_reference: str | None = None
    tap_response_code: str | None = None
    tap_response_message: str | None = None

    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
    