from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.coupons.models import Coupon, CouponRule, DiscountType
from app.modules.notifications.models import Notification, NotificationChannel, NotificationType
from app.modules.payments.models import Payment, PaymentRecordStatus
from app.modules.referrals.models import (
    Referral,
    ReferralCode,
    ReferralProgramSetting,
    ReferralReward,
    ReferralRewardStatus,
    ReferralStatus,
)
from app.modules.users.models import User


def get_program_setting(db: Session) -> ReferralProgramSetting:
    setting = db.query(ReferralProgramSetting).filter(ReferralProgramSetting.id == 1).first()
    if setting is None:
        setting = ReferralProgramSetting(id=1)
        db.add(setting)
        db.flush()
    return setting


def _generate_code(user: User) -> str:
    prefix = "".join(ch for ch in (user.first_name or "USER").upper() if ch.isalnum())[:6] or "USER"
    return f"{prefix}{secrets.token_hex(3).upper()}"


def ensure_referral_code(db: Session, user: User) -> ReferralCode:
    existing = db.query(ReferralCode).filter(ReferralCode.user_id == user.id).first()
    if existing:
        return existing

    for _ in range(10):
        code = _generate_code(user)
        if not db.query(ReferralCode.id).filter(ReferralCode.code == code).first():
            row = ReferralCode(user_id=user.id, code=code, is_active=True)
            db.add(row)
            db.flush()
            return row
    raise RuntimeError("Unable to generate unique referral code")


def validate_referral_code_for_registration(db: Session, code: str | None) -> ReferralCode | None:
    normalized = str(code or "").strip().upper()
    if not normalized:
        return None

    setting = get_program_setting(db)
    if not setting.is_active:
        raise HTTPException(status_code=400, detail="Referral program is currently inactive")

    referral_code = db.query(ReferralCode).filter(
        ReferralCode.code == normalized,
        ReferralCode.is_active.is_(True),
    ).first()
    if not referral_code:
        raise HTTPException(status_code=400, detail="Invalid or inactive referral code")
    return referral_code


def record_registration_referral(db: Session, referred_user: User, referral_code: ReferralCode | None) -> Referral | None:
    ensure_referral_code(db, referred_user)
    if referral_code is None:
        return None
    if referral_code.user_id == referred_user.id:
        raise HTTPException(status_code=400, detail="You cannot refer yourself")

    existing = db.query(Referral).filter(Referral.referred_user_id == referred_user.id).first()
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


def _unique_reward_coupon_code(db: Session, user_id: int) -> str:
    for _ in range(10):
        code = f"REF{user_id}-{secrets.token_hex(4).upper()}"
        if not db.query(Coupon.id).filter(Coupon.code == code).first():
            return code
    raise RuntimeError("Unable to generate referral reward coupon")


def qualify_referral_after_payment(db: Session, payment: Payment) -> ReferralReward | None:
    referral = db.query(Referral).filter(
        Referral.referred_user_id == payment.user_id,
        Referral.status == ReferralStatus.PENDING.value,
    ).first()
    if not referral:
        return None

    setting = get_program_setting(db)
    if not setting.is_active:
        return None

    if setting.referred_customer_must_make_first_payment:
        previous_paid = db.query(Payment.id).filter(
            Payment.user_id == payment.user_id,
            Payment.id != payment.id,
            Payment.status == PaymentRecordStatus.PAID.value,
        ).first()
        if previous_paid:
            referral.status = ReferralStatus.CANCELLED.value
            return None

    existing_reward = db.query(ReferralReward).filter(ReferralReward.referral_id == referral.id).first()
    if existing_reward:
        return existing_reward

    now = datetime.utcnow()
    expires_at = now + timedelta(days=int(setting.reward_expiry_days))
    coupon = Coupon(
        code=_unique_reward_coupon_code(db, referral.referrer_user_id),
        description=f"Referral reward for referral #{referral.id}",
        discount_type=DiscountType.FIXED.value,
        discount_value=float(setting.reward_amount),
        max_uses=1,
        used_count=0,
        min_order_amount=None,
        starts_at=now,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(coupon)
    db.flush()
    db.add(CouponRule(
        coupon_id=coupon.id,
        max_uses_per_user=1,
        allowed_user_id=referral.referrer_user_id,
        new_customers_only=False,
        source="referral",
    ))

    referral.status = ReferralStatus.REWARDED.value
    referral.qualified_subscription_id = payment.subscription_id
    referral.qualified_payment_id = payment.id
    referral.qualified_at = now
    referral.rewarded_at = now

    reward = ReferralReward(
        referral_id=referral.id,
        user_id=referral.referrer_user_id,
        coupon_id=coupon.id,
        reward_type="fixed_discount",
        reward_value=float(setting.reward_amount),
        status=ReferralRewardStatus.AVAILABLE.value,
        expires_at=expires_at,
    )
    db.add(reward)
    db.add(Notification(
        user_id=referral.referrer_user_id,
        title="Referral reward earned",
        message=(
            f"Your referral completed their first paid subscription. "
            f"You earned SAR {float(setting.reward_amount):.2f}. "
            f"Reward code: {coupon.code}"
        ),
        notification_type=NotificationType.PROMOTION.value,
        channel=NotificationChannel.IN_APP.value,
        is_read=False,
    ))
    db.flush()
    return reward


def mark_referral_reward_used_for_coupon(db: Session, coupon_id: int) -> None:
    reward = db.query(ReferralReward).filter(
        ReferralReward.coupon_id == coupon_id,
        ReferralReward.status == ReferralRewardStatus.AVAILABLE.value,
    ).first()
    if reward:
        reward.status = ReferralRewardStatus.USED.value
        reward.used_at = datetime.utcnow()
