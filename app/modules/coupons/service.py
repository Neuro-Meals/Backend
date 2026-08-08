from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.coupons.models import (
    Coupon,
    CouponApplicationStatus,
    CouponRedemption,
    CouponRule,
    DiscountType,
    PaymentCouponApplication,
)
from app.modules.payments.models import Payment, PaymentRecordStatus


MONEY = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def coupon_to_dict(coupon: Coupon) -> dict:
    rule = coupon.rule
    return {
        "id": coupon.id,
        "code": coupon.code,
        "description": coupon.description,
        "discount_type": coupon.discount_type,
        "discount_value": coupon.discount_value,
        "max_uses": coupon.max_uses,
        "used_count": coupon.used_count,
        "max_uses_per_user": rule.max_uses_per_user if rule else None,
        "min_order_amount": coupon.min_order_amount,
        "applicable_plan_id": rule.applicable_plan_id if rule else None,
        "allowed_user_id": rule.allowed_user_id if rule else None,
        "new_customers_only": bool(rule.new_customers_only) if rule else False,
        "source": rule.source if rule else "admin",
        "starts_at": coupon.starts_at,
        "expires_at": coupon.expires_at,
        "is_active": coupon.is_active,
        "created_at": coupon.created_at,
    }


def calculate_discount(coupon: Coupon, amount) -> Decimal:
    base = money(amount)
    value = Decimal(str(coupon.discount_value))

    if coupon.discount_type == DiscountType.PERCENTAGE.value:
        discount = base * (value / Decimal("100"))
    else:
        discount = value

    return min(base, discount).quantize(MONEY, rounding=ROUND_HALF_UP)


def validate_coupon_rules(
    db: Session,
    coupon: Coupon,
    amount,
    *,
    user_id: int,
    plan_id: int | None = None,
) -> None:
    now = datetime.utcnow()
    base = money(amount)
    rule = coupon.rule

    if not coupon.is_active:
        raise HTTPException(status_code=400, detail="Coupon is inactive")
    if coupon.starts_at and coupon.starts_at > now:
        raise HTTPException(status_code=400, detail="Coupon is not active yet")
    if coupon.expires_at and coupon.expires_at < now:
        raise HTTPException(status_code=400, detail="Coupon has expired")
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        raise HTTPException(status_code=400, detail="Coupon usage limit reached")
    if coupon.min_order_amount is not None and base < money(coupon.min_order_amount):
        raise HTTPException(status_code=400, detail="Amount is below coupon minimum")

    if not rule:
        return

    if rule.allowed_user_id is not None and rule.allowed_user_id != user_id:
        raise HTTPException(status_code=403, detail="Coupon is not assigned to this customer")

    if rule.applicable_plan_id is not None and rule.applicable_plan_id != plan_id:
        raise HTTPException(status_code=400, detail="Coupon does not apply to this plan")

    if rule.max_uses_per_user is not None:
        redeemed = (
            db.query(CouponRedemption)
            .filter(
                CouponRedemption.coupon_id == coupon.id,
                CouponRedemption.user_id == user_id,
            )
            .count()
        )
        if redeemed >= rule.max_uses_per_user:
            raise HTTPException(status_code=400, detail="Customer coupon usage limit reached")

    if rule.new_customers_only:
        paid_before = (
            db.query(Payment.id)
            .filter(
                Payment.user_id == user_id,
                Payment.status == PaymentRecordStatus.PAID.value,
            )
            .first()
        )
        if paid_before:
            raise HTTPException(status_code=400, detail="Coupon is for new customers only")


def get_valid_coupon(
    db: Session,
    code: str,
    amount,
    *,
    user_id: int,
    plan_id: int | None = None,
) -> Coupon:
    normalized = str(code or "").strip().upper()
    coupon = db.query(Coupon).filter(Coupon.code == normalized).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    validate_coupon_rules(
        db,
        coupon,
        amount,
        user_id=user_id,
        plan_id=plan_id,
    )
    return coupon


def set_payment_coupon_application(
    db: Session,
    *,
    payment: Payment,
    coupon: Coupon,
    original_amount,
) -> PaymentCouponApplication:
    original = money(original_amount)
    discount = calculate_discount(coupon, original)
    final = money(original - discount)

    application = (
        db.query(PaymentCouponApplication)
        .filter(PaymentCouponApplication.payment_id == payment.id)
        .first()
    )
    if application is None:
        application = PaymentCouponApplication(
            payment_id=payment.id,
            coupon_id=coupon.id,
            user_id=payment.user_id,
            subscription_id=payment.subscription_id,
            original_amount=original,
            discount_amount=discount,
            final_amount=final,
            status=CouponApplicationStatus.PENDING.value,
        )
        db.add(application)
    else:
        application.coupon_id = coupon.id
        application.original_amount = original
        application.discount_amount = discount
        application.final_amount = final
        application.status = CouponApplicationStatus.PENDING.value
        application.redeemed_at = None

    payment.amount = final
    return application


def release_payment_coupon_application(db: Session, payment_id: int) -> None:
    application = (
        db.query(PaymentCouponApplication)
        .filter(PaymentCouponApplication.payment_id == payment_id)
        .first()
    )
    if application and application.status == CouponApplicationStatus.PENDING.value:
        application.status = CouponApplicationStatus.RELEASED.value


def redeem_payment_coupon(db: Session, payment: Payment) -> CouponRedemption | None:
    existing = (
        db.query(CouponRedemption)
        .filter(CouponRedemption.payment_id == payment.id)
        .first()
    )
    if existing:
        return existing

    application = (
        db.query(PaymentCouponApplication)
        .filter(
            PaymentCouponApplication.payment_id == payment.id,
            PaymentCouponApplication.status == CouponApplicationStatus.PENDING.value,
        )
        .first()
    )
    if not application:
        return None

    coupon = (
        db.query(Coupon)
        .filter(Coupon.id == application.coupon_id)
        .with_for_update()
        .first()
    )
    if not coupon:
        return None

    redemption = CouponRedemption(
        coupon_id=coupon.id,
        user_id=payment.user_id,
        subscription_id=payment.subscription_id,
        payment_id=payment.id,
        original_amount=application.original_amount,
        discount_amount=application.discount_amount,
        final_amount=application.final_amount,
    )
    db.add(redemption)

    coupon.used_count = int(coupon.used_count or 0) + 1
    application.status = CouponApplicationStatus.REDEEMED.value
    application.redeemed_at = datetime.utcnow()
    return redemption
