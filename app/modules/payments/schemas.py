from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.models import (
    PaymentProvider,
    PaymentRecordStatus,
)


class CreateCheckoutRequest(BaseModel):
    subscription_id: int


class CreatePlanChangeCheckoutRequest(BaseModel):
    plan_change_id: int


class AttachMoyasarPaymentRequest(BaseModel):
    local_payment_id: int
    moyasar_payment_id: str = Field(
        min_length=10,
        max_length=255,
    )


class CheckoutResponse(BaseModel):
    payment_id: int

    # Amount in halalas: 250 SAR = 25000.
    amount: int
    currency: str
    description: str

    publishable_api_key: str
    callback_url: str

    metadata: dict[str, str]
    supported_networks: list[str]
    methods: list[str]

    status: PaymentRecordStatus


class PaymentResponse(BaseModel):
    id: int
    user_id: int
    subscription_id: int
    plan_change_id: int | None = None

    
    provider: PaymentProvider
    status: PaymentRecordStatus

    amount: Decimal
    currency: str

    provider_payment_id: str | None = None
    provider_reference: str | None = None
    provider_response_code: str | None = None
    provider_response_message: str | None = None
    provider_payload: dict[str, Any] | None = None

    callback_url: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MoyasarWebhookResponse(BaseModel):
    received: bool
    payment_id: int | None = None
    provider_payment_id: str | None = None
    status: str | None = None
    message: str | None = None