from __future__ import annotations

import hmac
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
    AttachMoyasarPaymentRequest,
    CheckoutResponse,
    CreateCheckoutRequest,
    CreatePlanChangeCheckoutRequest,
    MoyasarWebhookResponse,
    PaymentResponse,
)
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import (
    PaymentStatus,
    PlanChangeStatus,
    Subscription,
    SubscriptionPlanChange,
    SubscriptionStatus,
)
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/payments", tags=["Payments"])


# ---------------------------------------------------------------------------
# Configuration and shared helpers
# ---------------------------------------------------------------------------


def require_moyasar_configuration() -> None:
    missing: list[str] = []

    if not getattr(settings, "MOYASAR_PUBLISHABLE_KEY", None):
        missing.append("MOYASAR_PUBLISHABLE_KEY")

    if not getattr(settings, "MOYASAR_SECRET_KEY", None):
        missing.append("MOYASAR_SECRET_KEY")

    if not getattr(settings, "MOYASAR_API_URL", None):
        missing.append("MOYASAR_API_URL")

    if not getattr(settings, "MOYASAR_CALLBACK_URL", None):
        missing.append("MOYASAR_CALLBACK_URL")

    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing Moyasar configuration: {', '.join(missing)}",
        )


def amount_to_smallest_unit(
    amount: Decimal | float | int | str,
) -> int:
    """Convert SAR to halalas. Example: 250 SAR -> 25000."""
    decimal_amount = Decimal(str(amount))

    return int(
        (decimal_amount * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def moyasar_auth() -> tuple[str, str]:
    secret_key = getattr(settings, "MOYASAR_SECRET_KEY", None)

    if not secret_key:
        raise HTTPException(
            status_code=500,
            detail="Moyasar secret key is not configured",
        )

    # Moyasar uses HTTP Basic authentication: secret key as username,
    # and an empty password.
    return secret_key, ""


def extract_moyasar_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text or "Unknown Moyasar error"

    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("error")
        if message:
            return str(message)

        errors = payload.get("errors")
        if errors:
            return str(errors)

    return str(payload)


def retrieve_moyasar_payment(
    moyasar_payment_id: str,
) -> dict[str, Any]:
    require_moyasar_configuration()

    payment_id = str(moyasar_payment_id).strip()
    if not payment_id:
        raise HTTPException(
            status_code=400,
            detail="Moyasar payment ID is required",
        )

    url = (
        f"{settings.MOYASAR_API_URL.rstrip('/')}"
        f"/payments/{payment_id}"
    )

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                url,
                auth=moyasar_auth(),
                headers={"Accept": "application/json"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Moyasar: {exc}",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Could not retrieve Moyasar payment",
                "moyasar_status_code": response.status_code,
                "moyasar_error": extract_moyasar_error(response),
            },
        )

    payload = response.json()
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail="Moyasar returned an invalid payment response",
        )

    return payload


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


def activate_paid_subscription(
    db: Session,
    subscription: Subscription,
) -> None:
    subscription.payment_status = PaymentStatus.PAID
    subscription.status = SubscriptionStatus.ACTIVE

    if not subscription.start_date:
        duration_days = get_plan_duration_days(
            db=db,
            subscription=subscription,
        )

        subscription.start_date = datetime.utcnow()
        subscription.end_date = (
            subscription.start_date
            + timedelta(days=duration_days)
        )


def complete_upgrade_plan_change(
    db: Session,
    payment: Payment,
) -> None:
    if not payment.plan_change_id:
        return

    plan_change = (
        db.query(SubscriptionPlanChange)
        .filter(
            SubscriptionPlanChange.id == payment.plan_change_id
        )
        .first()
    )

    if not plan_change:
        raise HTTPException(
            status_code=404,
            detail="Plan change not found",
        )

    if plan_change.status == PlanChangeStatus.COMPLETED.value:
        return

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == plan_change.subscription_id
        )
        .first()
    )

    new_plan = (
        db.query(MealPlan)
        .filter(MealPlan.id == plan_change.new_plan_id)
        .first()
    )

    if not subscription or not new_plan:
        plan_change.status = PlanChangeStatus.FAILED.value
        raise HTTPException(
            status_code=404,
            detail="Subscription or new meal plan not found",
        )

    subscription.plan_id = new_plan.id
    subscription.amount = new_plan.price
    subscription.pending_plan_id = None
    subscription.plan_change_effective_at = None

    plan_change.status = PlanChangeStatus.COMPLETED.value
    plan_change.completed_at = datetime.utcnow()


def validate_remote_payment(
    payment: Payment,
    remote_payment: dict[str, Any],
) -> None:
    remote_payment_id = str(remote_payment.get("id") or "")

    if not remote_payment_id:
        raise HTTPException(
            status_code=400,
            detail="Moyasar response does not contain a payment ID",
        )

    if (
        payment.provider_payment_id
        and str(payment.provider_payment_id) != remote_payment_id
    ):
        raise HTTPException(
            status_code=400,
            detail="Moyasar payment ID does not match",
        )

    remote_amount = int(remote_payment.get("amount") or 0)
    expected_amount = amount_to_smallest_unit(payment.amount)

    if remote_amount != expected_amount:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Moyasar payment amount does not match",
                "expected": expected_amount,
                "received": remote_amount,
            },
        )

    remote_currency = str(
        remote_payment.get("currency") or ""
    ).upper()

    if remote_currency != str(payment.currency).upper():
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Moyasar payment currency does not match",
                "expected": str(payment.currency).upper(),
                "received": remote_currency,
            },
        )

    metadata = remote_payment.get("metadata") or {}
    metadata_payment_id = str(
        metadata.get("local_payment_id") or ""
    )

    if metadata_payment_id != str(payment.id):
        raise HTTPException(
            status_code=400,
            detail="Moyasar payment metadata does not match the local payment",
        )

    metadata_subscription_id = str(
        metadata.get("subscription_id") or ""
    )

    if (
        metadata_subscription_id
        and metadata_subscription_id != str(payment.subscription_id)
    ):
        raise HTTPException(
            status_code=400,
            detail="Moyasar subscription metadata does not match",
        )

    metadata_user_id = str(metadata.get("user_id") or "")

    if metadata_user_id and metadata_user_id != str(payment.user_id):
        raise HTTPException(
            status_code=400,
            detail="Moyasar user metadata does not match",
        )

    metadata_plan_change_id = str(
        metadata.get("plan_change_id") or ""
    )

    if payment.plan_change_id:
        if metadata_plan_change_id != str(payment.plan_change_id):
            raise HTTPException(
                status_code=400,
                detail="Moyasar plan-change metadata does not match",
            )


def process_moyasar_payment(
    db: Session,
    payment: Payment,
    remote_payment: dict[str, Any],
) -> None:
    remote_payment_id = str(remote_payment.get("id") or "")
    remote_status = str(
        remote_payment.get("status") or ""
    ).lower()

    source = remote_payment.get("source") or {}

    payment.provider_payment_id = remote_payment_id
    payment.provider_payload = remote_payment
    payment.provider_reference = (
        source.get("gateway_id")
        or source.get("reference_number")
        or remote_payment.get("invoice_id")
    )

    response_code = source.get("code")
    response_message = source.get("message")

    payment.provider_response_code = (
        str(response_code) if response_code is not None else None
    )
    payment.provider_response_message = (
        str(response_message) if response_message is not None else None
    )

    if remote_status in {"paid", "captured"}:
        payment.status = PaymentRecordStatus.PAID.value

        if payment.paid_at is None:
            payment.paid_at = datetime.utcnow()

        if payment.plan_change_id:
            complete_upgrade_plan_change(
                db=db,
                payment=payment,
            )
        else:
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

            activate_paid_subscription(
                db=db,
                subscription=subscription,
            )

    elif remote_status == "failed":
        payment.status = PaymentRecordStatus.FAILED.value

    elif remote_status in {"voided", "cancelled", "canceled"}:
        payment.status = PaymentRecordStatus.CANCELLED.value

    elif remote_status == "refunded":
        # This assumes REFUNDED exists in PaymentRecordStatus.
        payment.status = PaymentRecordStatus.REFUNDED.value

    else:
        # initiated, authorized, verified, or another non-final state
        payment.status = PaymentRecordStatus.PENDING.value


def build_checkout_response(
    payment: Payment,
    description: str,
    metadata: dict[str, str],
) -> CheckoutResponse:
    require_moyasar_configuration()

    return CheckoutResponse(
        payment_id=payment.id,
        amount=amount_to_smallest_unit(payment.amount),
        currency=str(payment.currency).upper(),
        description=description,
        publishable_api_key=settings.MOYASAR_PUBLISHABLE_KEY,
        callback_url=settings.MOYASAR_CALLBACK_URL,
        metadata=metadata,
        supported_networks=["mada", "visa", "mastercard"],
        methods=["creditcard"],
        status=PaymentRecordStatus(payment.status),
    )


# ---------------------------------------------------------------------------
# Customer checkout endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/create-checkout",
    response_model=CheckoutResponse,
)
def create_checkout(
    payload: CreateCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_moyasar_configuration()

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
            detail="Subscription is already paid",
        )

    payment = (
        db.query(Payment)
        .filter(
            Payment.subscription_id == subscription.id,
            Payment.user_id == current_user.id,
            Payment.plan_change_id.is_(None),
            Payment.provider == PaymentProvider.MOYASAR.value,
            Payment.status == PaymentRecordStatus.PENDING.value,
        )
        .order_by(Payment.id.desc())
        .first()
    )

    if payment is None:
        payment = Payment(
            user_id=current_user.id,
            subscription_id=subscription.id,
            plan_change_id=None,
            provider=PaymentProvider.MOYASAR.value,
            status=PaymentRecordStatus.PENDING.value,
            amount=subscription.amount,
            currency=settings.PAYMENT_CURRENCY.upper(),
            callback_url=settings.MOYASAR_CALLBACK_URL,
        )

        db.add(payment)
        db.commit()
        db.refresh(payment)

    return build_checkout_response(
        payment=payment,
        description=f"NutrioMeals subscription #{subscription.id}",
        metadata={
            "local_payment_id": str(payment.id),
            "subscription_id": str(subscription.id),
            "user_id": str(current_user.id),
            "payment_type": "subscription",
        },
    )


@router.post(
    "/create-plan-change-checkout",
    response_model=CheckoutResponse,
)
def create_plan_change_checkout(
    payload: CreatePlanChangeCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_moyasar_configuration()

    plan_change = (
        db.query(SubscriptionPlanChange)
        .filter(
            SubscriptionPlanChange.id == payload.plan_change_id,
            SubscriptionPlanChange.user_id == current_user.id,
        )
        .first()
    )

    if not plan_change:
        raise HTTPException(
            status_code=404,
            detail="Plan change not found",
        )

    if plan_change.status != PlanChangeStatus.PENDING_PAYMENT.value:
        raise HTTPException(
            status_code=400,
            detail="Plan change is not awaiting payment",
        )

    if Decimal(str(plan_change.amount_difference)) <= Decimal("0"):
        raise HTTPException(
            status_code=400,
            detail="Plan change does not require payment",
        )

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == plan_change.subscription_id,
            Subscription.user_id == current_user.id,
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    payment = (
        db.query(Payment)
        .filter(
            Payment.plan_change_id == plan_change.id,
            Payment.user_id == current_user.id,
            Payment.provider == PaymentProvider.MOYASAR.value,
            Payment.status == PaymentRecordStatus.PENDING.value,
        )
        .order_by(Payment.id.desc())
        .first()
    )

    if payment is None:
        payment = Payment(
            user_id=current_user.id,
            subscription_id=subscription.id,
            plan_change_id=plan_change.id,
            provider=PaymentProvider.MOYASAR.value,
            status=PaymentRecordStatus.PENDING.value,
            amount=plan_change.amount_difference,
            currency=settings.PAYMENT_CURRENCY.upper(),
            callback_url=settings.MOYASAR_CALLBACK_URL,
        )

        db.add(payment)
        db.commit()
        db.refresh(payment)

    return build_checkout_response(
        payment=payment,
        description=f"NutrioMeals plan upgrade #{plan_change.id}",
        metadata={
            "local_payment_id": str(payment.id),
            "subscription_id": str(subscription.id),
            "plan_change_id": str(plan_change.id),
            "user_id": str(current_user.id),
            "payment_type": "plan_change",
        },
    )


@router.post(
    "/attach-moyasar-payment",
    response_model=PaymentResponse,
)
def attach_moyasar_payment(
    payload: AttachMoyasarPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payload.local_payment_id,
            Payment.user_id == current_user.id,
            Payment.provider == PaymentProvider.MOYASAR.value,
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Local payment not found",
        )

    duplicate = (
        db.query(Payment)
        .filter(
            Payment.provider_payment_id == payload.moyasar_payment_id,
            Payment.id != payment.id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=(
                "This Moyasar payment is already attached "
                "to another local payment"
            ),
        )

    remote_payment = retrieve_moyasar_payment(
        payload.moyasar_payment_id
    )

    validate_remote_payment(
        payment=payment,
        remote_payment=remote_payment,
    )

    payment.provider_payment_id = str(remote_payment["id"])
    payment.provider_payload = remote_payment

    # Process immediately in case the payment is already paid.
    process_moyasar_payment(
        db=db,
        payment=payment,
        remote_payment=remote_payment,
    )

    db.commit()
    db.refresh(payment)

    return payment


@router.get(
    "/verify/{payment_id}",
    response_model=PaymentResponse,
)
def verify_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.user_id == current_user.id,
            Payment.provider == PaymentProvider.MOYASAR.value,
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found",
        )

    if not payment.provider_payment_id:
        raise HTTPException(
            status_code=400,
            detail="Moyasar payment ID has not been attached",
        )

    remote_payment = retrieve_moyasar_payment(
        payment.provider_payment_id
    )

    validate_remote_payment(
        payment=payment,
        remote_payment=remote_payment,
    )

    process_moyasar_payment(
        db=db,
        payment=payment,
        remote_payment=remote_payment,
    )

    db.commit()
    db.refresh(payment)

    return payment


# ---------------------------------------------------------------------------
# Moyasar webhook
# ---------------------------------------------------------------------------


@router.post(
    "/webhook/moyasar",
    response_model=MoyasarWebhookResponse,
)
async def moyasar_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        event = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload",
        ) from exc

    received_secret = str(event.get("secret_token") or "")
    expected_secret = str(
        getattr(settings, "MOYASAR_WEBHOOK_SECRET", "") or ""
    )

    if not expected_secret:
        raise HTTPException(
            status_code=500,
            detail="Moyasar webhook secret is not configured",
        )

    if not hmac.compare_digest(received_secret, expected_secret):
        raise HTTPException(
            status_code=401,
            detail="Invalid Moyasar webhook secret",
        )

    event_type = str(event.get("type") or "")
    event_data = event.get("data") or {}
    moyasar_payment_id = str(event_data.get("id") or "")

    if not moyasar_payment_id:
        return MoyasarWebhookResponse(
            received=True,
            message="No Moyasar payment ID supplied",
        )

    payment = (
        db.query(Payment)
        .filter(
            Payment.provider_payment_id == moyasar_payment_id
        )
        .first()
    )

    if payment is None:
        metadata = event_data.get("metadata") or {}
        local_payment_id = metadata.get("local_payment_id")

        if local_payment_id and str(local_payment_id).isdigit():
            payment = (
                db.query(Payment)
                .filter(Payment.id == int(local_payment_id))
                .first()
            )

    if payment is None:
        # Return HTTP 200 to acknowledge an old or unknown event.
        return MoyasarWebhookResponse(
            received=True,
            provider_payment_id=moyasar_payment_id,
            message="Local payment record not found",
        )

    remote_payment = retrieve_moyasar_payment(
        moyasar_payment_id
    )

    if payment.provider_payment_id is None:
        payment.provider_payment_id = moyasar_payment_id

    validate_remote_payment(
        payment=payment,
        remote_payment=remote_payment,
    )

    process_moyasar_payment(
        db=db,
        payment=payment,
        remote_payment=remote_payment,
    )

    db.commit()
    db.refresh(payment)

    return MoyasarWebhookResponse(
        received=True,
        payment_id=payment.id,
        provider_payment_id=payment.provider_payment_id,
        status=payment.status,
        message=f"Processed {event_type}",
    )


# ---------------------------------------------------------------------------
# Customer and admin reporting endpoints
# ---------------------------------------------------------------------------


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
    provider: PaymentProvider | None = Query(None),
    user_id: int | None = Query(None),
    subscription_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Payment)

    if status:
        query = query.filter(Payment.status == status.value)

    if provider:
        query = query.filter(Payment.provider == provider.value)

    if user_id:
        query = query.filter(Payment.user_id == user_id)

    if subscription_id:
        query = query.filter(
            Payment.subscription_id == subscription_id
        )

    total = query.count()

    payments = (
        query.order_by(Payment.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    results: list[dict[str, Any]] = []

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
                .filter(MealPlan.id == subscription.plan_id)
                .first()
            )

        plan_change = None
        if payment.plan_change_id:
            plan_change = (
                db.query(SubscriptionPlanChange)
                .filter(
                    SubscriptionPlanChange.id
                    == payment.plan_change_id
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
                "plan_change": {
                    "id": plan_change.id,
                    "status": (
                        plan_change.status.value
                        if hasattr(plan_change.status, "value")
                        else plan_change.status
                    ),
                    "new_plan_id": plan_change.new_plan_id,
                    "amount_difference": (
                        plan_change.amount_difference
                    ),
                }
                if plan_change
                else None,
                "payment": {
                    "provider": payment.provider,
                    "status": payment.status,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "provider_payment_id": (
                        payment.provider_payment_id
                    ),
                    "provider_reference": (
                        payment.provider_reference
                    ),
                    "provider_response_code": (
                        payment.provider_response_code
                    ),
                    "provider_response_message": (
                        payment.provider_response_message
                    ),
                    "callback_url": payment.callback_url,
                    "paid_at": payment.paid_at,
                    "created_at": payment.created_at,
                    "updated_at": payment.updated_at,
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