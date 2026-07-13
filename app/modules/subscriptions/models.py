from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class SubscriptionStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class PlanChangeType(str, Enum):
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"


class PlanChangeStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Subscription(Base):
    __tablename__ = "subscriptions"

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

    plan_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    pending_plan_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    status: Mapped[SubscriptionStatus] = mapped_column(
        SqlEnum(SubscriptionStatus),
        default=SubscriptionStatus.PENDING_PAYMENT,
        nullable=False,
    )

    payment_status: Mapped[PaymentStatus] = mapped_column(
        SqlEnum(PaymentStatus),
        default=PaymentStatus.UNPAID,
        nullable=False,
    )

    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    start_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    end_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    total_paused_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    pause_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    plan_change_effective_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    auto_renew: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
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


class SubscriptionPause(Base):
    __tablename__ = "subscription_pauses"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey(
            "subscriptions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    paused_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    resumed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class SubscriptionPlanChange(Base):
    __tablename__ = "subscription_plan_changes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey(
            "subscriptions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    old_plan_id: Mapped[int] = mapped_column(
        ForeignKey(
            "meal_plans.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    new_plan_id: Mapped[int] = mapped_column(
        ForeignKey(
            "meal_plans.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    change_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    old_amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    new_amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    amount_difference: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
    )

    effective_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )