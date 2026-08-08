from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.coupons.models import (
    Coupon,
    CouponRule,
    DiscountType,
)
from app.modules.notifications.models import (
    Notification,
    NotificationChannel,
    NotificationType,
)
from app.modules.payments.models import (
    Payment,
    PaymentRecordStatus,
)
from app.modules.referrals.models import (
    Referral,
    ReferralCode,
    ReferralCommissionScope,
    ReferralEarning,
    ReferralEarningStatus,
    ReferralProgramSetting,
    ReferralReward,
    ReferralRewardMode,
    ReferralRewardStatus,
    ReferralStatus,
)
from app.modules.users.models import User


MONEY = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(
        MONEY,
        rounding=ROUND_HALF_UP,
    )


def get_program_setting(
    db: Session,
) -> ReferralProgramSetting:
    setting = (
        db.query(ReferralProgramSetting)
        .filter(ReferralProgramSetting.id == 1)
        .first()
    )

    if setting is None:
        setting = ReferralProgramSetting(
            id=1,
            reward_mode=ReferralRewardMode.FIXED_FIRST_PAYMENT.value,
            reward_value=100.0,
            reward_amount=100.0,
            commission_scope=(
                ReferralCommissionScope.FIRST_PAYMENT_ONLY.value
            ),
        )
        db.add(setting)
        db.flush()

    return setting


def sync_program_setting_legacy_fields(
    setting: ReferralProgramSetting,
) -> None:
    """
    Keep old frontend/backend clients compatible.

    reward_amount is the historical setting name. For fixed modes it mirrors
    reward_value. For percentage mode it still returns reward_value, but the
    new reward_mode tells clients that the number means percent.
    """
    setting.reward_amount = float(
        setting.reward_value
        or setting.reward_amount
        or 0
    )

    setting.referred_customer_must_make_first_payment = (
        setting.commission_scope
        == ReferralCommissionScope.FIRST_PAYMENT_ONLY.value
        or setting.reward_mode
        == ReferralRewardMode.FIXED_FIRST_PAYMENT.value
    )


def _generate_code(user: User) -> str:
    prefix = "".join(
        ch
        for ch in (user.first_name or "USER").upper()
        if ch.isalnum()
    )[:6] or "USER"

    return f"{prefix}{secrets.token_hex(3).upper()}"


def ensure_referral_code(
    db: Session,
    user: User,
) -> ReferralCode:
    existing = (
        db.query(ReferralCode)
        .filter(ReferralCode.user_id == user.id)
        .first()
    )

    if existing:
        return existing

    for _ in range(10):
        code = _generate_code(user)

        exists = (
            db.query(ReferralCode.id)
            .filter(ReferralCode.code == code)
            .first()
        )

        if not exists:
            row = ReferralCode(
                user_id=user.id,
                code=code,
                is_active=True,
            )
            db.add(row)
            db.flush()
            return row

    raise RuntimeError(
        "Unable to generate unique referral code"
    )


def validate_referral_code_for_registration(
    db: Session,
    code: str | None,
) -> ReferralCode | None:
    normalized = str(code or "").strip().upper()

    if not normalized:
        return None

    setting = get_program_setting(db)

    if not setting.is_active:
        raise HTTPException(
            status_code=400,
            detail="Referral program is currently inactive",
        )

    referral_code = (
        db.query(ReferralCode)
        .filter(
            ReferralCode.code == normalized,
            ReferralCode.is_active.is_(True),
        )
        .first()
    )

    if not referral_code:
        raise HTTPException(
            status_code=400,
            detail="Invalid or inactive referral code",
        )

    return referral_code


def record_registration_referral(
    db: Session,
    referred_user: User,
    referral_code: ReferralCode | None,
) -> Referral | None:
    ensure_referral_code(
        db,
        referred_user,
    )

    if referral_code is None:
        return None

    if referral_code.user_id == referred_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot refer yourself",
        )

    existing = (
        db.query(Referral)
        .filter(
            Referral.referred_user_id == referred_user.id
        )
        .first()
    )

    if existing:
        return existing

    row = Referral(
        referrer_user_id=referral_code.user_id,
        referred_user_id=referred_user.id,
        referral_code_id=referral_code.id,
        status=ReferralStatus.PENDING.value,
    )

    db.add(row)
    db.flush()

    return row


def _unique_reward_coupon_code(
    db: Session,
    user_id: int,
) -> str:
    for _ in range(20):
        code = (
            f"REF{user_id}-"
            f"{secrets.token_hex(4).upper()}"
        )

        exists = (
            db.query(Coupon.id)
            .filter(Coupon.code == code)
            .first()
        )

        if not exists:
            return code

    raise RuntimeError(
        "Unable to generate referral reward coupon"
    )


def _successful_subscription_payment_count(
    db: Session,
    user_id: int,
    *,
    exclude_payment_id: int | None = None,
) -> int:
    query = db.query(Payment.id).filter(
        Payment.user_id == user_id,
        Payment.plan_change_id.is_(None),
        Payment.status == PaymentRecordStatus.PAID.value,
    )

    if exclude_payment_id is not None:
        query = query.filter(
            Payment.id != exclude_payment_id
        )

    return query.count()


def _is_payment_eligible(
    db: Session,
    payment: Payment,
    setting: ReferralProgramSetting,
) -> bool:
    if (
        payment.status
        != PaymentRecordStatus.PAID.value
    ):
        return False

    if payment.plan_change_id is not None:
        return False

    first_only = (
        setting.reward_mode
        == ReferralRewardMode.FIXED_FIRST_PAYMENT.value
        or setting.commission_scope
        == ReferralCommissionScope.FIRST_PAYMENT_ONLY.value
    )

    if first_only:
        previous_paid = (
            _successful_subscription_payment_count(
                db,
                payment.user_id,
                exclude_payment_id=payment.id,
            )
        )

        if previous_paid > 0:
            return False

    return True


def calculate_referral_reward(
    setting: ReferralProgramSetting,
    payment_amount,
) -> Decimal:
    base = money(payment_amount)

    mode = str(setting.reward_mode)
    rate = Decimal(
        str(
            setting.reward_value
            or setting.reward_amount
            or 0
        )
    )

    if mode == ReferralRewardMode.PERCENTAGE_OF_PAYMENT.value:
        amount = (
            base
            * (rate / Decimal("100"))
        )
    else:
        amount = rate

    amount = amount.quantize(
        MONEY,
        rounding=ROUND_HALF_UP,
    )

    if setting.max_reward_per_payment is not None:
        cap = money(
            setting.max_reward_per_payment
        )
        amount = min(
            amount,
            cap,
        )

    # Never create negative credit.
    return max(
        amount,
        Decimal("0.00"),
    )


def _create_private_credit_coupon(
    db: Session,
    *,
    user_id: int,
    earning_id: int,
    reward_amount: Decimal,
    expires_at: datetime,
) -> Coupon:
    coupon = Coupon(
        code=_unique_reward_coupon_code(
            db,
            user_id,
        ),
        description=(
            f"Referral earning #{earning_id}"
        ),
        discount_type=DiscountType.FIXED.value,
        discount_value=float(reward_amount),
        max_uses=1,
        used_count=0,
        min_order_amount=None,
        starts_at=datetime.utcnow(),
        expires_at=expires_at,
        is_active=True,
    )

    db.add(coupon)
    db.flush()

    db.add(
        CouponRule(
            coupon_id=coupon.id,
            max_uses_per_user=1,
            allowed_user_id=user_id,
            new_customers_only=False,
            source="referral_earning",
        )
    )

    return coupon


def process_referral_earning_after_payment(
    db: Session,
    payment: Payment,
) -> ReferralEarning | None:
    """
    Idempotently create one referral earning for a qualifying successful
    payment.

    The referred user remains permanently attributed to their original
    referrer. When commission_scope=every_payment, later successful
    subscription payments can therefore generate additional earnings.
    """

    existing = (
        db.query(ReferralEarning)
        .filter(
            ReferralEarning.payment_id == payment.id
        )
        .first()
    )

    if existing:
        return existing

    referral = (
        db.query(Referral)
        .filter(
            Referral.referred_user_id == payment.user_id,
            Referral.status != ReferralStatus.CANCELLED.value,
        )
        .first()
    )

    if not referral:
        return None

    setting = get_program_setting(db)

    if not setting.is_active:
        return None

    if not _is_payment_eligible(
        db,
        payment,
        setting,
    ):
        return None

    reward_amount = calculate_referral_reward(
        setting,
        payment.amount,
    )

    if reward_amount <= 0:
        return None

    now = datetime.utcnow()
    expires_at = (
        now
        + timedelta(
            days=int(
                setting.reward_expiry_days
            )
        )
    )

    earning = ReferralEarning(
        referral_id=referral.id,
        referral_code_id=referral.referral_code_id,
        referrer_user_id=referral.referrer_user_id,
        referred_user_id=referral.referred_user_id,
        subscription_id=payment.subscription_id,
        payment_id=payment.id,
        coupon_id=None,
        reward_mode=str(setting.reward_mode),
        reward_rate=money(
            setting.reward_value
            or setting.reward_amount
            or 0
        ),
        payment_amount=money(
            payment.amount
        ),
        reward_amount=reward_amount,
        status=ReferralEarningStatus.AVAILABLE.value,
        expires_at=expires_at,
        earned_at=now,
    )

    db.add(earning)
    db.flush()

    coupon = _create_private_credit_coupon(
        db,
        user_id=referral.referrer_user_id,
        earning_id=earning.id,
        reward_amount=reward_amount,
        expires_at=expires_at,
    )

    earning.coupon_id = coupon.id

    # Referral-level fields capture the FIRST qualifying event.
    if referral.qualified_payment_id is None:
        referral.qualified_payment_id = payment.id
        referral.qualified_subscription_id = (
            payment.subscription_id
        )
        referral.qualified_at = now

    referral.status = ReferralStatus.REWARDED.value
    referral.rewarded_at = now

    mode_label = {
        ReferralRewardMode.FIXED_PER_PAYMENT.value:
            "fixed reward",
        ReferralRewardMode.PERCENTAGE_OF_PAYMENT.value:
            "percentage commission",
        ReferralRewardMode.FIXED_FIRST_PAYMENT.value:
            "first-payment reward",
    }.get(
        str(setting.reward_mode),
        "referral reward",
    )

    db.add(
        Notification(
            user_id=referral.referrer_user_id,
            title="Referral earning received",
            message=(
                f"You earned SAR "
                f"{float(reward_amount):.2f} "
                f"as a {mode_label} from a successful "
                f"referred subscription payment. "
                f"Credit code: {coupon.code}"
            ),
            notification_type=(
                NotificationType.PROMOTION.value
            ),
            channel=(
                NotificationChannel.IN_APP.value
            ),
            is_read=False,
        )
    )

    db.flush()

    return earning


def qualify_referral_after_payment(
    db: Session,
    payment: Payment,
):
    """
    Backwards-compatible alias used by existing payment code.
    """
    return process_referral_earning_after_payment(
        db,
        payment,
    )


def mark_referral_reward_used_for_coupon(
    db: Session,
    coupon_id: int,
) -> None:
    """
    Mark both legacy ReferralReward and new ReferralEarning records used
    when their private coupon is successfully redeemed.
    """

    now = datetime.utcnow()

    reward = (
        db.query(ReferralReward)
        .filter(
            ReferralReward.coupon_id == coupon_id,
            ReferralReward.status
            == ReferralRewardStatus.AVAILABLE.value,
        )
        .first()
    )

    if reward:
        reward.status = (
            ReferralRewardStatus.USED.value
        )
        reward.used_at = now

    earning = (
        db.query(ReferralEarning)
        .filter(
            ReferralEarning.coupon_id == coupon_id,
            ReferralEarning.status
            == ReferralEarningStatus.AVAILABLE.value,
        )
        .first()
    )

    if earning:
        earning.status = (
            ReferralEarningStatus.USED.value
        )
        earning.used_at = now
