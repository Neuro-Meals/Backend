from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import PaymentStatus, Subscription, SubscriptionStatus
from app.modules.subscriptions.schemas import (
    AdminUpdateSubscription,
    SubscriptionCreate,
    SubscriptionResponse,
)
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.post("/", response_model=SubscriptionResponse)
def create_subscription(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.query(MealPlan).filter(
        MealPlan.id == payload.plan_id,
        MealPlan.is_active == True,
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found or inactive")

    existing = db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.status.in_([
            SubscriptionStatus.PENDING_PAYMENT,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PAUSED,
        ]),
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already have an active or pending subscription",
        )

    subscription = Subscription(
        user_id=current_user.id,
        plan_id=plan.id,
        amount=plan.price,
        status=SubscriptionStatus.PENDING_PAYMENT,
        payment_status=PaymentStatus.UNPAID,
        notes=payload.notes,
    )

    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return subscription


@router.get("/my", response_model=list[SubscriptionResponse])
def my_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id)
        .order_by(Subscription.id.desc())
        .all()
    )


@router.get("/")
def list_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.FINANCE_MANAGER)
    ),
    status: SubscriptionStatus | None = Query(None),
    payment_status: PaymentStatus | None = Query(None),
    user_id: int | None = Query(None),
    plan_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Subscription)

    if status:
        query = query.filter(Subscription.status == status)

    if payment_status:
        query = query.filter(Subscription.payment_status == payment_status)

    if user_id:
        query = query.filter(Subscription.user_id == user_id)

    if plan_id:
        query = query.filter(Subscription.plan_id == plan_id)

    total = query.count()

    subscriptions = (
        query.order_by(Subscription.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": subscriptions,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if current_user.role == UserRole.CUSTOMER and subscription.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    return subscription


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
def admin_update_subscription(
    subscription_id: int,
    payload: AdminUpdateSubscription,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.FINANCE_MANAGER)
    ),
):
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(subscription, field, value)

    if subscription.status == SubscriptionStatus.ACTIVE and not subscription.start_date:
        plan = db.query(MealPlan).filter(MealPlan.id == subscription.plan_id).first()
        subscription.start_date = datetime.utcnow()
        subscription.end_date = datetime.utcnow() + timedelta(days=plan.duration_days)

    db.commit()
    db.refresh(subscription)

    return subscription


@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
def cancel_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if current_user.role == UserRole.CUSTOMER and subscription.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    subscription.status = SubscriptionStatus.CANCELLED
    subscription.cancelled_at = datetime.utcnow()

    db.commit()
    db.refresh(subscription)

    return subscription