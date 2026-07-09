from datetime import datetime, timedelta

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.payments.models import Payment, PaymentRecordStatus
from app.modules.payments.schemas import (
    CheckoutResponse,
    CreateCheckoutRequest,
    PaymentResponse,
)
from app.modules.subscriptions.models import (
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.plans.models import MealPlan
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/payments", tags=["Payments"])

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/create-checkout", response_model=CheckoutResponse)
def create_checkout(
    payload: CreateCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = db.query(Subscription).filter(
        Subscription.id == payload.subscription_id,
        Subscription.user_id == current_user.id,
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if subscription.payment_status == PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="Subscription already paid")

    payment = Payment(
        user_id=current_user.id,
        subscription_id=subscription.id,
        amount=subscription.amount,
        currency="usd",
        status=PaymentRecordStatus.PENDING.value,
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    amount_in_cents = int(subscription.amount * 100)

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        customer_email=current_user.email,
        line_items=[
            {
                "price_data": {
                    "currency": payment.currency,
                    "product_data": {
                        "name": f"Nutrio Meals Subscription #{subscription.id}",
                    },
                    "unit_amount": amount_in_cents,
                },
                "quantity": 1,
            }
        ],
        success_url=f"{settings.FRONTEND_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}&payment_id={payment.id}",
        cancel_url=f"{settings.FRONTEND_CANCEL_URL}?payment_id={payment.id}",
        metadata={
            "payment_id": str(payment.id),
            "subscription_id": str(subscription.id),
            "user_id": str(current_user.id),
        },
    )

    payment.stripe_checkout_session_id = session.id
    payment.checkout_url = session.url

    db.commit()
    db.refresh(payment)

    return CheckoutResponse(
        payment_id=payment.id,
        checkout_url=session.url,
        stripe_checkout_session_id=session.id,
    )


@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        payment_id = session.get("metadata", {}).get("payment_id")
        subscription_id = session.get("metadata", {}).get("subscription_id")

        payment = db.query(Payment).filter(Payment.id == int(payment_id)).first()
        subscription = db.query(Subscription).filter(Subscription.id == int(subscription_id)).first()

        if payment and subscription:
            payment.status = PaymentRecordStatus.PAID.value
            payment.stripe_payment_intent_id = session.get("payment_intent")
            payment.paid_at = datetime.utcnow()

            subscription.payment_status = PaymentStatus.PAID
            subscription.status = SubscriptionStatus.ACTIVE

            if not subscription.start_date:
                subscription.start_date = datetime.utcnow()
                subscription.end_date = datetime.utcnow() + timedelta(days=30)

            db.commit()

    return {"received": True}


@router.get("/my", response_model=list[PaymentResponse])
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
        query = query.filter(Payment.status == status)

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
            .filter(Subscription.id == payment.subscription_id)
            .first()
        )

        plan = None

        if subscription:
            plan = (
                db.query(MealPlan)
                .filter(MealPlan.id == subscription.plan_id)
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
                        if user else None
                    ),
                    "email": user.email if user else None,
                    "phone": user.phone if user else None,
                    "role": user.role.value if user else None,
                    "is_verified": user.is_verified if user else None,
                },

                "subscription": {
                    "id": subscription.id if subscription else None,
                    "plan_id": subscription.plan_id if subscription else None,
                    "plan_name": plan.name_en if plan else None,
                    "status": (
                        subscription.status.value
                        if subscription else None
                    ),
                    "payment_status": (
                        subscription.payment_status.value
                        if subscription else None
                    ),
                    "start_date": (
                        subscription.start_date
                        if subscription else None
                    ),
                    "end_date": (
                        subscription.end_date
                        if subscription else None
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
                    "stripe_checkout_session_id": payment.stripe_checkout_session_id,
                    "stripe_payment_intent_id": payment.stripe_payment_intent_id,
                },
            }
        )

    return {
        "data": results,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }
    
@router.get("/verify-session/{session_id}", response_model=PaymentResponse)
def verify_stripe_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter(
        Payment.stripe_checkout_session_id == session_id,
        Payment.user_id == current_user.id,
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    session = stripe.checkout.Session.retrieve(session_id)

    if session.payment_status != "paid":
        raise HTTPException(
            status_code=400,
            detail="Payment is not completed yet",
        )

    subscription = db.query(Subscription).filter(
        Subscription.id == payment.subscription_id,
        Subscription.user_id == current_user.id,
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    payment.status = PaymentRecordStatus.PAID.value
    payment.stripe_payment_intent_id = session.payment_intent
    payment.paid_at = datetime.utcnow()

    subscription.payment_status = PaymentStatus.PAID
    subscription.status = SubscriptionStatus.ACTIVE

    if not subscription.start_date:
        subscription.start_date = datetime.utcnow()
        subscription.end_date = datetime.utcnow() + timedelta(days=30)

    db.commit()
    db.refresh(payment)

    return payment    