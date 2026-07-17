from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class PaymentProvider(str, Enum):
    TAP = "tap"          # temporarily keep for old records
    MOYASAR = "moyasar"

    # Keep temporarily if old Stripe records exist.
    STRIPE = "stripe"


class PaymentRecordStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    subscription_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    
    plan_change_id: Mapped[int | None] = mapped_column(
    Integer,
    nullable=True,
    index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        default=PaymentProvider.MOYASAR.value,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default=PaymentRecordStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="SAR",
        nullable=False,
    )

    # Tap identifiers
    provider_charge_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )

    provider_payment_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    provider_gateway_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    provider_response_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    provider_response_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    checkout_url: Mapped[str | None] = mapped_column(
        String(1500),
        nullable=True,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Keep these temporarily so old Stripe data is not destroyed.
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )