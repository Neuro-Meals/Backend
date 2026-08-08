from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class DiscountType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class CouponApplicationStatus(str, Enum):
    PENDING = "pending"
    REDEEMED = "redeemed"
    RELEASED = "released"


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    discount_type: Mapped[str] = mapped_column(String(50), nullable=False)
    discount_value: Mapped[float] = mapped_column(Float, nullable=False)

    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)

    min_order_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    rule: Mapped["CouponRule | None"] = relationship(
        "CouponRule",
        back_populates="coupon",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CouponRule(Base):
    """Extra rules kept in a separate table so the legacy coupons table stays compatible."""

    __tablename__ = "coupon_rules"

    coupon_id: Mapped[int] = mapped_column(
        ForeignKey("coupons.id", ondelete="CASCADE"),
        primary_key=True,
    )
    max_uses_per_user: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applicable_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("meal_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    allowed_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    new_customers_only: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(30),
        default="admin",
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    coupon: Mapped["Coupon"] = relationship("Coupon", back_populates="rule")


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_coupon_redemption_payment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coupon_id: Mapped[int] = mapped_column(
        ForeignKey("coupons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    final_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaymentCouponApplication(Base):
    """Coupon selected for a local payment before the provider payment succeeds."""

    __tablename__ = "payment_coupon_applications"
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_payment_coupon_application_payment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    coupon_id: Mapped[int] = mapped_column(
        ForeignKey("coupons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    final_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        default=CouponApplicationStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
