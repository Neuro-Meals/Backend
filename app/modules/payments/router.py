from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.payments.models import (
    Payment,
    PaymentProvider,
    PaymentRecordStatus,
)
from app.modules.payments.schemas import (
    CheckoutResponse,
    CreateCheckoutRequest,
    PaymentResponse,
)
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import (
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/payments", tags=["Payments"])


TAP_SUCCESS_STATUS = "CAPTURED"

TAP_PENDING_STATUSES = {
    "INITIATED",
    "IN_PROGRESS",
    "PENDING",
}

TAP_CANCELLED_STATUSES = {
    "CANCELLED",
    "ABANDONED",
}

TAP_FAILED_STATUSES = {
    "FAILED",
    "DECLINED",
    "RESTRICTED",
    "VOID",
    "TIMEDOUT",
    "UNKNOWN",
}


# -------------------------------------------------------------------
# Tap helpers
# -------------------------------------------------------------------

def tap_headers() -> dict[str, str]:
    if not settings.TAP_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Tap secret key is not configured",
        )

    return {
        "Authorization": f"Bearer {settings.TAP_SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "lang_code": "en",
    }


def extract_tap_error(response: httpx.Response) -> str:
    try:
        data = response.json()

        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            first_error = errors[0]

            if isinstance(first_error, dict):
                return (
                    first_error.get("description")
                    or first_error.get("message")
                    or str(first_error)
                )

        return (
            data.get("message")
            or data.get("description")
            or str(data)
        )

    except Exception:
        return response.text or "Unknown Tap error"


def create_tap_charge(payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{settings.TAP_API_URL.rstrip('/')}/charges/"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                headers=tap_headers(),
                json=payload,
            )

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Tap: {exc}",
        )

    if response.status_code not in {200, 201}:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Tap rejected the charge request",
                "tap_status_code": response.status_code,
                "tap_error": extract_tap_error(response),
            },
        )

    return response.json()


def retrieve_tap_charge(charge_id: str) -> dict[str, Any]:
    url = f"{settings.TAP_API_URL.rstrip('/')}/charges/{charge_id}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                url,
                headers=tap_headers(),
            )

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Tap: {exc}",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Could not retrieve Tap charge",
                "tap_status_code": response.status_code,
                "tap_error": extract_tap_error(response),
            },
        )

    return response.json()


def split_phone_number(phone: str | None) -> tuple[str, str]:
    """
    Tap expects:
        country_code: "966"
        number: "5XXXXXXXX"

    Examples:
        +966512345678 -> ("966", "512345678")
        966512345678  -> ("966", "512345678")
    """
    digits = "".join(character for character in (phone or "") if character.isdigit())

    if digits.startswith("966") and len(digits) > 3:
        return "966", digits[3:]

    if digits.startswith("0") and len(digits) > 1:
        return "966", digits[1:]

    if digits:
        return "966", digits

    # Tap requires either phone or email; email is already supplied.
    return "966", "500000000"


def get_plan_duration_days(
    db: Session,
    subscription: Subscription,
) -> int:
    plan = (
        db.query(MealPlan)
        .filter(MealPlan.id == subscription.plan_id)
        .first()
    )

    if plan and plan.duration_days:
        return int(plan.duration_days)

    return 30


def update_payment_from_tap_charge(
    db: Session,
    payment: Payment,
    subscription: Subscription,
    charge: dict[str, Any],
) -> None:
    tap_status = str(charge.get("status", "")).upper()

    references = charge.get("reference") or {}
    response_data = charge.get("response") or {}

    payment.tap_charge_id = charge.get("id") or payment.tap_charge_id
    payment.tap_payment_reference = references.get("payment")
    payment.tap_gateway_reference = references.get("gateway")
    payment.tap_response_code = response_data.get("code")
    payment.tap_response_message = response_data.get("message")

    if tap_status == TAP_SUCCESS_STATUS:
        payment.status = PaymentRecordStatus.PAID.value

        if not payment.paid_at:
            payment.paid_at = datetime.utcnow()

        subscription.payment_status = PaymentStatus.PAID
        subscription.status = SubscriptionStatus.ACTIVE

        if not subscription.start_date:
            duration_days = get_plan_duration_days(db, subscription)

            subscription.start_date = datetime.utcnow()
            subscription.end_date = (
                subscription.start_date
                + timedelta(days=duration_days)
            )

    elif tap_status in TAP_CANCELLED_STATUSES:
        payment.status = PaymentRecordStatus.CANCELLED.value

    elif tap_status in TAP_FAILED_STATUSES:
        payment.status = PaymentRecordStatus.FAILED.value

    else:
        payment.status = PaymentRecordStatus.PENDING.value


def currency_decimal_places(currency: str) -> int:
    three_decimal_currencies = {
        "BHD",
        "JOD",
        "KWD",
        "OMR",
    }

    return 3 if currency.upper() in three_decimal_currencies else 2


def format_tap_amount(amount: Any, currency: str) -> str:
    decimal_places = currency_decimal_places(currency)

    quantizer = (
        Decimal("0.001")
        if decimal_places == 3
        else Decimal("0.01")
    )

    rounded = Decimal(str(amount)).quantize(
        quantizer,
        rounding=ROUND_HALF_UP,
    )

    return f"{rounded:.{decimal_places}f}"


def validate_tap_hashstring(
    payload: dict[str, Any],
    received_hashstring: str | None,
) -> bool:
    if not received_hashstring:
        return False

    reference = payload.get("reference") or {}
    transaction = payload.get("transaction") or {}

    charge_id = payload.get("id", "")
    amount = format_tap_amount(
        payload.get("amount", 0),
        payload.get("currency", "SAR"),
    )
    currency = payload.get("currency", "")
    gateway_reference = reference.get("gateway", "")
    payment_reference = reference.get("payment", "")
    status = payload.get("status", "")
    created = transaction.get("created", "")

    value_to_hash = (
        f"x_id{charge_id}"
        f"x_amount{amount}"
        f"x_currency{currency}"
        f"x_gateway_reference{gateway_reference}"
        f"x_payment_reference{payment_reference}"
        f"x_status{status}"
        f"x_created{created}"
    )

    calculated_hash = hmac.new(
        settings.TAP_SECRET_KEY.encode("utf-8"),
        value_to_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        calculated_hash.lower(),
        received_hashstring.lower(),
    )


def find_payment_from_charge(
    db: Session,
    charge: dict[str, Any],
) -> Payment | None:
    charge_id = charge.get("id")

    if charge_id:
        payment = (
            db.query(Payment)
            .filter(Payment.tap_charge_id == charge_id)
            .first()
        )

        if payment:
            return payment

    metadata = charge.get("metadata") or {}
    payment_id = metadata.get("payment_id")

    if payment_id and str(payment_id).isdigit():
        return (
            db.query(Payment)
            .filter(Payment.id == int(payment_id))
            .first()
        )

    reference = charge.get("reference") or {}
    transaction_reference = reference.get("transaction", "")

    if transaction_reference.startswith("payment_"):
        possible_id = transaction_reference.removeprefix("payment_")

        if possible_id.isdigit():
            return (
                db.query(Payment)
                .filter(Payment.id == int(possible_id))
                .first()
            )

    return None


# -------------------------------------------------------------------
# Customer payment endpoints
# -------------------------------------------------------------------

@router.post(
    "/create-checkout",
    response_model=CheckoutResponse,
)
def create_checkout(
    payload: CreateCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == payload.subscription_id,
            Subscription.user_id == current_user.id,
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    if subscription.payment_status == PaymentStatus.PAID:
        raise HTTPException(
            status_code=400,
            detail="Subscription already paid",
        )

    # Prevent several pending checkout records for the same subscription.
    existing_payment = (
        db.query(Payment)
        .filter(
            Payment.subscription_id == subscription.id,
            Payment.user_id == current_user.id,
            Payment.provider == PaymentProvider.TAP.value,
            Payment.status == PaymentRecordStatus.PENDING.value,
        )
        .order_by(Payment.id.desc())
        .first()
    )

    if existing_payment and existing_payment.checkout_url:
        return CheckoutResponse(
            payment_id=existing_payment.id,
            checkout_url=existing_payment.checkout_url,
            tap_charge_id=existing_payment.tap_charge_id or "",
            status=existing_payment.status,
        )

    payment = Payment(
        user_id=current_user.id,
        subscription_id=subscription.id,
        provider=PaymentProvider.TAP.value,
        status=PaymentRecordStatus.PENDING.value,
        amount=float(subscription.amount),
        currency=settings.PAYMENT_CURRENCY.upper(),
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    country_code, phone_number = split_phone_number(current_user.phone)

    tap_payload = {
        "amount": round(float(subscription.amount), 2),
        "currency": settings.PAYMENT_CURRENCY.upper(),
        "customer_initiated": True,
        "threeDSecure": True,
        "save_card": False,
        "description": (
            f"NutrioMeals subscription #{subscription.id}"
        ),
        "statement_descriptor": "NutrioMeals",
        "metadata": {
            "payment_id": str(payment.id),
            "subscription_id": str(subscription.id),
            "user_id": str(current_user.id),
        },
        "reference": {
            "transaction": f"payment_{payment.id}",
            "order": f"subscription_{subscription.id}",
            "idempotent": f"tap_payment_{payment.id}",
        },
        "receipt": {
            "email": True,
            "sms": False,
        },
        "customer": {
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "phone": {
                "country_code": country_code,
                "number": phone_number,
            },
        },
        "merchant": {
            "id": settings.TAP_MERCHANT_ID,
        },
        # Shows all payment methods enabled by Tap for this merchant.
        "source": {
            "id": "src_all",
        },
        "post": {
            "url": settings.TAP_WEBHOOK_URL,
        },
        "redirect": {
            "url": settings.FRONTEND_SUCCESS_URL,
        },
    }

    try:
        charge = create_tap_charge(tap_payload)

        charge_id = charge.get("id")
        tap_status = str(charge.get("status", "")).upper()
        transaction = charge.get("transaction") or {}
        checkout_url = transaction.get("url")

        if not charge_id:
            raise HTTPException(
                status_code=502,
                detail="Tap did not return a charge ID",
            )

        if not checkout_url and tap_status != TAP_SUCCESS_STATUS:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Tap did not return a checkout URL",
                    "tap_response": charge,
                },
            )

        payment.tap_charge_id = charge_id
        payment.checkout_url = checkout_url

        update_payment_from_tap_charge(
            db=db,
            payment=payment,
            subscription=subscription,
            charge=charge,
        )

        db.commit()
        db.refresh(payment)

        return CheckoutResponse(
            payment_id=payment.id,
            checkout_url=checkout_url or settings.FRONTEND_SUCCESS_URL,
            tap_charge_id=charge_id,
            status=payment.status,
        )

    except HTTPException:
        payment.status = PaymentRecordStatus.FAILED.value
        db.commit()
        raise

    except Exception as exc:
        payment.status = PaymentRecordStatus.FAILED.value
        payment.tap_response_message = str(exc)

        db.commit()

        raise HTTPException(
            status_code=500,
            detail="Could not create Tap checkout",
        )


@router.get(
    "/verify-charge/{charge_id}",
    response_model=PaymentResponse,
)
def verify_tap_charge(
    charge_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (
        db.query(Payment)
        .filter(
            Payment.tap_charge_id == charge_id,
            Payment.user_id == current_user.id,
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found",
        )

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == payment.subscription_id,
            Subscription.user_id == current_user.id,
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    charge = retrieve_tap_charge(charge_id)

    # Important server-side checks.
    tap_amount = round(float(charge.get("amount", 0)), 2)
    expected_amount = round(float(payment.amount), 2)

    if tap_amount != expected_amount:
        raise HTTPException(
            status_code=400,
            detail="Tap payment amount does not match",
        )

    if str(charge.get("currency", "")).upper() != payment.currency.upper():
        raise HTTPException(
            status_code=400,
            detail="Tap payment currency does not match",
        )

    merchant = charge.get("merchant") or {}
    charge_merchant_id = str(
        merchant.get("id")
        or charge.get("merchant_id")
        or ""
    )

    if (
        charge_merchant_id
        and charge_merchant_id != str(settings.TAP_MERCHANT_ID)
    ):
        raise HTTPException(
            status_code=400,
            detail="Tap merchant does not match",
        )

    update_payment_from_tap_charge(
        db=db,
        payment=payment,
        subscription=subscription,
        charge=charge,
    )

    db.commit()
    db.refresh(payment)

    if payment.status != PaymentRecordStatus.PAID.value:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Payment is not completed",
                "tap_status": charge.get("status"),
                "tap_response": (
                    charge.get("response") or {}
                ).get("message"),
            },
        )

    return payment


# -------------------------------------------------------------------
# Tap webhook
# -------------------------------------------------------------------

@router.post("/webhook/tap")
async def tap_webhook(
    request: Request,
    hashstring: str | None = Header(
        default=None,
        alias="hashstring",
    ),
    db: Session = Depends(get_db),
):
    try:
        payload = await request.json()

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload",
        )

    if not validate_tap_hashstring(payload, hashstring):
        raise HTTPException(
            status_code=400,
            detail="Invalid Tap webhook hashstring",
        )

    payment = find_payment_from_charge(db, payload)

    if not payment:
        # Return 200 so Tap does not keep retrying an unknown old charge.
        return {
            "received": True,
            "message": "Payment record not found",
        }

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == payment.subscription_id,
            Subscription.user_id == payment.user_id,
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    # Retrieve directly from Tap instead of trusting the webhook body alone.
    charge_id = payload.get("id")

    if not charge_id:
        raise HTTPException(
            status_code=400,
            detail="Tap charge ID is missing",
        )

    charge = retrieve_tap_charge(charge_id)

    tap_amount = round(float(charge.get("amount", 0)), 2)
    expected_amount = round(float(payment.amount), 2)

    if tap_amount != expected_amount:
        raise HTTPException(
            status_code=400,
            detail="Tap webhook amount does not match",
        )

    if str(charge.get("currency", "")).upper() != payment.currency.upper():
        raise HTTPException(
            status_code=400,
            detail="Tap webhook currency does not match",
        )

    update_payment_from_tap_charge(
        db=db,
        payment=payment,
        subscription=subscription,
        charge=charge,
    )

    db.commit()

    return {
        "received": True,
        "payment_id": payment.id,
        "tap_charge_id": payment.tap_charge_id,
        "status": payment.status,
    }


# -------------------------------------------------------------------
# Payment history
# -------------------------------------------------------------------

@router.get(
    "/my",
    response_model=list[PaymentResponse],
)
def my_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Payment)
        .filter(Payment.user_id == current_user.id)
        .order_by(Payment.id.desc())
        .all()
    )


@router.get("/")
def list_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.FINANCE_MANAGER,
        )
    ),
    status: PaymentRecordStatus | None = Query(None),
    user_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Payment)

    if status:
        query = query.filter(Payment.status == status.value)

    if user_id:
        query = query.filter(Payment.user_id == user_id)

    total = query.count()

    payments = (
        query.order_by(Payment.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    results = []

    for payment in payments:
        user = (
            db.query(User)
            .filter(User.id == payment.user_id)
            .first()
        )

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.id == payment.subscription_id
            )
            .first()
        )

        plan = None

        if subscription:
            plan = (
                db.query(MealPlan)
                .filter(
                    MealPlan.id == subscription.plan_id
                )
                .first()
            )

        results.append(
            {
                "id": payment.id,
                "customer": {
                    "id": user.id if user else None,
                    "first_name": user.first_name if user else None,
                    "last_name": user.last_name if user else None,
                    "full_name": (
                        f"{user.first_name} {user.last_name}"
                        if user
                        else None
                    ),
                    "email": user.email if user else None,
                    "phone": user.phone if user else None,
                    "role": (
                        user.role.value
                        if user and hasattr(user.role, "value")
                        else user.role if user else None
                    ),
                    "is_verified": (
                        user.is_verified if user else None
                    ),
                },
                "subscription": {
                    "id": subscription.id if subscription else None,
                    "plan_id": (
                        subscription.plan_id
                        if subscription
                        else None
                    ),
                    "plan_name": plan.name_en if plan else None,
                    "status": (
                        subscription.status.value
                        if subscription
                        and hasattr(subscription.status, "value")
                        else subscription.status
                        if subscription
                        else None
                    ),
                    "payment_status": (
                        subscription.payment_status.value
                        if subscription
                        and hasattr(
                            subscription.payment_status,
                            "value",
                        )
                        else subscription.payment_status
                        if subscription
                        else None
                    ),
                    "start_date": (
                        subscription.start_date
                        if subscription
                        else None
                    ),
                    "end_date": (
                        subscription.end_date
                        if subscription
                        else None
                    ),
                },
                "payment": {
                    "provider": payment.provider,
                    "status": payment.status,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "paid_at": payment.paid_at,
                    "created_at": payment.created_at,
                    "checkout_url": payment.checkout_url,
                    "tap_charge_id": payment.tap_charge_id,
                    "tap_payment_reference": (
                        payment.tap_payment_reference
                    ),
                    "tap_gateway_reference": (
                        payment.tap_gateway_reference
                    ),
                    "tap_response_code": (
                        payment.tap_response_code
                    ),
                    "tap_response_message": (
                        payment.tap_response_message
                    ),
                },
            }
        )

    return {
        "data": results,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (
                (total + limit - 1) // limit
                if total
                else 0
            ),
        },
    }