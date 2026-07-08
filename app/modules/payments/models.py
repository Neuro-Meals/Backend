from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class PaymentProvider(str, Enum):
    STRIPE = "stripe"


class PaymentRecordStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    subscription_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    provider: Mapped[str] = mapped_column(
        String(50),
        default=PaymentProvider.STRIPE.value,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default=PaymentRecordStatus.PENDING.value,
        nullable=False,
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)

    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    checkout_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )