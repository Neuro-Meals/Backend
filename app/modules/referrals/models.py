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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ReferralStatus(str, Enum):
    PENDING = "pending"
    QUALIFIED = "qualified"
    REWARDED = "rewarded"
    CANCELLED = "cancelled"


class ReferralRewardStatus(str, Enum):
    AVAILABLE = "available"
    USED = "used"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ReferralRewardMode(str, Enum):
    """
    How an individual qualifying payment creates earnings.

    FIXED_PER_PAYMENT:
        Example: SAR 50 for every qualifying successful payment.

    PERCENTAGE_OF_PAYMENT:
        Example: 5% of each qualifying successful payment.

    FIXED_FIRST_PAYMENT:
        Example: SAR 100 only for the referred customer's first
        successful subscription payment.
    """

    FIXED_PER_PAYMENT = "fixed_per_payment"
    PERCENTAGE_OF_PAYMENT = "percentage_of_payment"
    FIXED_FIRST_PAYMENT = "fixed_first_payment"


class ReferralCommissionScope(str, Enum):
    FIRST_PAYMENT_ONLY = "first_payment_only"
    EVERY_PAYMENT = "every_payment"


class ReferralEarningStatus(str, Enum):
    AVAILABLE = "available"
    USED = "used"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ReferralProgramSetting(Base):
    __tablename__ = "referral_program_settings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Legacy compatibility. Existing frontend versions may still read/write
    # reward_amount. The service synchronizes it with reward_value for fixed
    # reward modes.
    reward_amount: Mapped[float] = mapped_column(
        Float,
        default=100.0,
        nullable=False,
    )

    reward_mode: Mapped[str] = mapped_column(
        String(40),
        default=ReferralRewardMode.FIXED_FIRST_PAYMENT.value,
        nullable=False,
    )

    reward_value: Mapped[float] = mapped_column(
        Float,
        default=100.0,
        nullable=False,
    )

    commission_scope: Mapped[str] = mapped_column(
        String(40),
        default=ReferralCommissionScope.FIRST_PAYMENT_ONLY.value,
        nullable=False,
    )

    max_reward_per_payment: Mapped[float | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    reward_expiry_days: Mapped[int] = mapped_column(
        Integer,
        default=90,
        nullable=False,
    )

    # Legacy flag retained for compatibility with the first referral version.
    referred_customer_must_make_first_payment: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class ReferralCode(Base):
    __tablename__ = "referral_codes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


class Referral(Base):
    __tablename__ = "referrals"

    __table_args__ = (
        UniqueConstraint(
            "referred_user_id",
            name="uq_referral_referred_user",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    referrer_user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    referred_user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    referral_code_id: Mapped[int] = mapped_column(
        ForeignKey(
            "referral_codes.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default=ReferralStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    # First qualifying subscription/payment are retained as referral-level
    # audit fields even when the program pays commission on every payment.
    qualified_subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "subscriptions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    qualified_payment_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "payments.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    qualified_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    rewarded_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


class ReferralReward(Base):
    """
    Legacy first-version reward table.

    Kept so existing reward coupons and frontend data remain valid.
    New commission accounting is recorded in ReferralEarning.
    """

    __tablename__ = "referral_rewards"

    __table_args__ = (
        UniqueConstraint(
            "referral_id",
            name="uq_referral_reward_referral",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    referral_id: Mapped[int] = mapped_column(
        ForeignKey(
            "referrals.id",
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

    coupon_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "coupons.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    reward_type: Mapped[str] = mapped_column(
        String(30),
        default="fixed_discount",
        nullable=False,
    )

    reward_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default=ReferralRewardStatus.AVAILABLE.value,
        nullable=False,
        index=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


class ReferralEarning(Base):
    """
    Immutable-ish referral commission ledger.

    One successful qualifying Payment can create at most one earning.
    The generated coupon turns the earning into spendable NutrioMeals credit.
    """

    __tablename__ = "referral_earnings"

    __table_args__ = (
        UniqueConstraint(
            "payment_id",
            name="uq_referral_earning_payment",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    referral_id: Mapped[int] = mapped_column(
        ForeignKey(
            "referrals.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    referral_code_id: Mapped[int] = mapped_column(
        ForeignKey(
            "referral_codes.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    referrer_user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    referred_user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
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

    payment_id: Mapped[int] = mapped_column(
        ForeignKey(
            "payments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    coupon_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "coupons.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    reward_mode: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    reward_rate: Mapped[float] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    payment_amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    reward_amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default=ReferralEarningStatus.AVAILABLE.value,
        nullable=False,
        index=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    earned_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
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
