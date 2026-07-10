from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import (
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.subscriptions.schemas import (
    AdminUpdateSubscription,
    SubscriptionCreate,
    SubscriptionResponse,
)
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


def enum_value(value):
    if value is None:
        return None

    return value.value if hasattr(value, "value") else value


# =========================================================
# CREATE SUBSCRIPTION
# =========================================================

@router.post("/", response_model=SubscriptionResponse)
def create_subscription(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = (
        db.query(MealPlan)
        .filter(
            MealPlan.id == payload.plan_id,
            MealPlan.is_active.is_(True),
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Plan not found or inactive",
        )

    existing_subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
            Subscription.status.in_(
                [
                    SubscriptionStatus.PENDING_PAYMENT,
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.PAUSED,
                ]
            ),
        )
        .first()
    )

    if existing_subscription:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "You already have an active or pending subscription",
                "subscription_id": existing_subscription.id,
                "status": enum_value(existing_subscription.status),
                "payment_status": enum_value(
                    existing_subscription.payment_status
                ),
            },
        )

    subscription = Subscription(
        user_id=current_user.id,
        plan_id=plan.id,
        amount=plan.price,
        status=SubscriptionStatus.PENDING_PAYMENT,
        payment_status=PaymentStatus.UNPAID,
        notes=payload.notes or "",
    )

    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return subscription


# =========================================================
# CUSTOMER SUBSCRIPTIONS
# =========================================================

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


# =========================================================
# ADMIN LIST SUBSCRIPTIONS
# =========================================================

@router.get("/")
def list_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.FINANCE_MANAGER,
        )
    ),
    status: SubscriptionStatus | None = Query(None),
    payment_status: PaymentStatus | None = Query(None),
    user_id: int | None = Query(None),
    plan_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Subscription)

    if status is not None:
        query = query.filter(Subscription.status == status)

    if payment_status is not None:
        query = query.filter(
            Subscription.payment_status == payment_status
        )

    if user_id is not None:
        query = query.filter(Subscription.user_id == user_id)

    if plan_id is not None:
        query = query.filter(Subscription.plan_id == plan_id)

    total = query.count()

    subscriptions = (
        query.order_by(Subscription.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    results = []

    for subscription in subscriptions:
        user = (
            db.query(User)
            .filter(User.id == subscription.user_id)
            .first()
        )

        plan = (
            db.query(MealPlan)
            .filter(MealPlan.id == subscription.plan_id)
            .first()
        )

        results.append(
            {
                "id": subscription.id,
                "status": enum_value(subscription.status),
                "payment_status": enum_value(
                    subscription.payment_status
                ),
                "amount": subscription.amount,
                "start_date": subscription.start_date,
                "end_date": subscription.end_date,
                "cancelled_at": subscription.cancelled_at,
                "notes": subscription.notes,
                "created_at": subscription.created_at,
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
                        enum_value(user.role)
                        if user
                        else None
                    ),
                    "is_verified": (
                        user.is_verified
                        if user
                        else None
                    ),
                },
                "plan": {
                    "id": plan.id if plan else None,
                    "name_en": plan.name_en if plan else None,
                    "name_ar": plan.name_ar if plan else None,
                    "plan_type": (
                        enum_value(plan.plan_type)
                        if plan
                        else None
                    ),
                    "goal": (
                        enum_value(plan.goal)
                        if plan
                        else None
                    ),
                    "price": plan.price if plan else None,
                    "duration_days": (
                        plan.duration_days
                        if plan
                        else None
                    ),
                    "meals_per_day": (
                        plan.meals_per_day
                        if plan
                        else None
                    ),
                    "total_meals": (
                        plan.total_meals
                        if plan
                        else None
                    ),
                    "image_url": (
                        plan.image_url
                        if plan
                        else None
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
            "pages": (total + limit - 1) // limit,
        },
    }


# =========================================================
# GET ONE SUBSCRIPTION
# =========================================================

@router.get("/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    if (
        current_user.role == UserRole.CUSTOMER
        and subscription.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Not allowed",
        )

    return subscription


# =========================================================
# ADMIN UPDATE SUBSCRIPTION
# =========================================================

@router.patch(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
)
def admin_update_subscription(
    subscription_id: int,
    payload: AdminUpdateSubscription,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.FINANCE_MANAGER,
        )
    ),
):
    subscription = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(subscription, field, value)

    if (
        subscription.status == SubscriptionStatus.ACTIVE
        and not subscription.start_date
    ):
        plan = (
            db.query(MealPlan)
            .filter(MealPlan.id == subscription.plan_id)
            .first()
        )

        if not plan:
            raise HTTPException(
                status_code=404,
                detail="Subscription plan not found",
            )

        subscription.start_date = datetime.utcnow()
        subscription.end_date = (
            subscription.start_date
            + timedelta(days=plan.duration_days)
        )

    db.commit()
    db.refresh(subscription)

    return subscription


# =========================================================
# CANCEL SUBSCRIPTION
# =========================================================

@router.post(
    "/{subscription_id}/cancel",
    response_model=SubscriptionResponse,
)
def cancel_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    if (
        current_user.role == UserRole.CUSTOMER
        and subscription.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Not allowed",
        )

    if subscription.status == SubscriptionStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail="Subscription is already cancelled",
        )

    subscription.status = SubscriptionStatus.CANCELLED
    subscription.cancelled_at = datetime.utcnow()

    db.commit()
    db.refresh(subscription)

    return subscription