from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import (
    get_current_user,
    require_roles,
)
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import (
    PaymentStatus,
    PlanChangeStatus,
    PlanChangeType,
    Subscription,
    SubscriptionPause,
    SubscriptionPlanChange,
    SubscriptionStatus,
)
from app.modules.subscriptions.schemas import (
    AdminUpdateSubscription,
    ChangePlanRequest,
    ChangePlanResult,
    PauseHistoryResponse,
    PauseSubscriptionRequest,
    PauseSubscriptionResponse,
    PlanChangeResponse,
    ResumeSubscriptionResponse,
    SubscriptionCreate,
    SubscriptionResponse,
)
from app.modules.users.models import User, UserRole


router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions"],
)


MAX_PAUSES_PER_SUBSCRIPTION = 2
MAX_TOTAL_PAUSE_DAYS = 7


def enum_value(value):
    if value is None:
        return None

    return value.value if hasattr(value, "value") else value


def get_subscription_or_404(
    db: Session,
    subscription_id: int,
) -> Subscription:
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

    return subscription


def ensure_subscription_access(
    subscription: Subscription,
    current_user: User,
) -> None:
    allowed_admin_roles = {
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN,
        UserRole.FINANCE_MANAGER,
    }

    if (
        current_user.role not in allowed_admin_roles
        and subscription.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this subscription",
        )


def get_active_pause(
    db: Session,
    subscription_id: int,
) -> SubscriptionPause | None:
    return (
        db.query(SubscriptionPause)
        .filter(
            SubscriptionPause.subscription_id == subscription_id,
            SubscriptionPause.resumed_at.is_(None),
        )
        .order_by(SubscriptionPause.id.desc())
        .first()
    )


@router.post(
    "/",
    response_model=SubscriptionResponse,
)
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
                "message": (
                    "You already have an active, paused, "
                    "or pending subscription"
                ),
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


@router.get(
    "/my",
    response_model=list[SubscriptionResponse],
)
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

        pending_plan = None

        if subscription.pending_plan_id:
            pending_plan = (
                db.query(MealPlan)
                .filter(
                    MealPlan.id == subscription.pending_plan_id
                )
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
                "paused_at": subscription.paused_at,
                "pause_count": subscription.pause_count,
                "total_paused_seconds": (
                    subscription.total_paused_seconds
                ),
                "total_paused_days": round(
                    subscription.total_paused_seconds / 86400,
                    2,
                ),
                "pending_plan_id": subscription.pending_plan_id,
                "plan_change_effective_at": (
                    subscription.plan_change_effective_at
                ),
                "cancelled_at": subscription.cancelled_at,
                "auto_renew": subscription.auto_renew,
                "notes": subscription.notes,
                "created_at": subscription.created_at,
                "customer": {
                    "id": user.id if user else None,
                    "first_name": (
                        user.first_name if user else None
                    ),
                    "last_name": (
                        user.last_name if user else None
                    ),
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
                    "price": plan.price if plan else None,
                    "duration_days": (
                        plan.duration_days if plan else None
                    ),
                    "meals_per_day": (
                        plan.meals_per_day if plan else None
                    ),
                    "total_meals": (
                        plan.total_meals if plan else None
                    ),
                },
                "pending_plan": {
                    "id": pending_plan.id,
                    "name_en": pending_plan.name_en,
                    "name_ar": pending_plan.name_ar,
                    "price": pending_plan.price,
                }
                if pending_plan
                else None,
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


# =========================================================
# PAUSE SUBSCRIPTION
# =========================================================

@router.post(
    "/{subscription_id}/pause",
    response_model=PauseSubscriptionResponse,
)
def pause_subscription(
    subscription_id: int,
    payload: PauseSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = get_subscription_or_404(
        db,
        subscription_id,
    )

    ensure_subscription_access(
        subscription,
        current_user,
    )

    if subscription.status == SubscriptionStatus.PAUSED:
        raise HTTPException(
            status_code=400,
            detail="Subscription is already paused",
        )

    if subscription.status != SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail="Only active subscriptions can be paused",
        )

    if subscription.payment_status != PaymentStatus.PAID:
        raise HTTPException(
            status_code=400,
            detail="Only paid subscriptions can be paused",
        )

    if subscription.pause_count >= MAX_PAUSES_PER_SUBSCRIPTION:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Maximum pause limit reached. "
                f"Only {MAX_PAUSES_PER_SUBSCRIPTION} pauses are allowed."
            ),
        )

    maximum_seconds = MAX_TOTAL_PAUSE_DAYS * 86400

    if subscription.total_paused_seconds >= maximum_seconds:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Maximum total pause duration of "
                f"{MAX_TOTAL_PAUSE_DAYS} days has been reached"
            ),
        )

    paused_at = datetime.utcnow()

    pause_record = SubscriptionPause(
        subscription_id=subscription.id,
        user_id=subscription.user_id,
        reason=payload.reason,
        paused_at=paused_at,
    )

    subscription.status = SubscriptionStatus.PAUSED
    subscription.paused_at = paused_at
    subscription.pause_count += 1

    db.add(pause_record)
    db.commit()
    db.refresh(subscription)

    return PauseSubscriptionResponse(
        message="Subscription paused successfully",
        subscription_id=subscription.id,
        status=enum_value(subscription.status),
        paused_at=paused_at,
        pause_count=subscription.pause_count,
    )


# =========================================================
# RESUME SUBSCRIPTION
# =========================================================

@router.post(
    "/{subscription_id}/resume",
    response_model=ResumeSubscriptionResponse,
)
def resume_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = get_subscription_or_404(
        db,
        subscription_id,
    )

    ensure_subscription_access(
        subscription,
        current_user,
    )

    if subscription.status != SubscriptionStatus.PAUSED:
        raise HTTPException(
            status_code=400,
            detail="Subscription is not paused",
        )

    if not subscription.paused_at:
        raise HTTPException(
            status_code=400,
            detail="Subscription pause date is missing",
        )

    active_pause = get_active_pause(
        db,
        subscription.id,
    )

    if not active_pause:
        raise HTTPException(
            status_code=400,
            detail="Active pause history was not found",
        )

    resumed_at = datetime.utcnow()
    paused_duration = resumed_at - subscription.paused_at
    paused_seconds = max(
        int(paused_duration.total_seconds()),
        0,
    )

    old_end_date = subscription.end_date

    if subscription.end_date:
        subscription.end_date = (
            subscription.end_date
            + timedelta(seconds=paused_seconds)
        )

    subscription.total_paused_seconds += paused_seconds
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.paused_at = None

    active_pause.resumed_at = resumed_at
    active_pause.duration_seconds = paused_seconds

    db.commit()
    db.refresh(subscription)

    return ResumeSubscriptionResponse(
        message="Subscription resumed successfully",
        subscription_id=subscription.id,
        status=enum_value(subscription.status),
        paused_seconds=paused_seconds,
        paused_days=round(paused_seconds / 86400, 2),
        old_end_date=old_end_date,
        new_end_date=subscription.end_date,
        total_paused_seconds=(
            subscription.total_paused_seconds
        ),
    )


@router.get(
    "/{subscription_id}/pauses",
    response_model=list[PauseHistoryResponse],
)
def get_subscription_pauses(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = get_subscription_or_404(
        db,
        subscription_id,
    )

    ensure_subscription_access(
        subscription,
        current_user,
    )

    return (
        db.query(SubscriptionPause)
        .filter(
            SubscriptionPause.subscription_id
            == subscription.id
        )
        .order_by(SubscriptionPause.id.desc())
        .all()
    )


# =========================================================
# CHANGE PLAN
# =========================================================

@router.post(
    "/{subscription_id}/change-plan",
    response_model=ChangePlanResult,
)
def change_subscription_plan(
    subscription_id: int,
    payload: ChangePlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = get_subscription_or_404(
        db,
        subscription_id,
    )

    ensure_subscription_access(
        subscription,
        current_user,
    )

    if subscription.status not in {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAUSED,
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only active or paused subscriptions "
                "can change plans"
            ),
        )

    if subscription.payment_status != PaymentStatus.PAID:
        raise HTTPException(
            status_code=400,
            detail="Subscription must be paid before changing plan",
        )

    if subscription.plan_id == payload.new_plan_id:
        raise HTTPException(
            status_code=400,
            detail="You are already subscribed to this plan",
        )

    current_plan = (
        db.query(MealPlan)
        .filter(MealPlan.id == subscription.plan_id)
        .first()
    )

    new_plan = (
        db.query(MealPlan)
        .filter(
            MealPlan.id == payload.new_plan_id,
            MealPlan.is_active.is_(True),
        )
        .first()
    )

    if not current_plan:
        raise HTTPException(
            status_code=404,
            detail="Current subscription plan not found",
        )

    if not new_plan:
        raise HTTPException(
            status_code=404,
            detail="New plan not found or inactive",
        )

    existing_change = (
        db.query(SubscriptionPlanChange)
        .filter(
            SubscriptionPlanChange.subscription_id
            == subscription.id,
            SubscriptionPlanChange.status.in_(
                [
                    PlanChangeStatus.PENDING_PAYMENT.value,
                    PlanChangeStatus.SCHEDULED.value,
                ]
            ),
        )
        .first()
    )

    if existing_change:
        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    "This subscription already has a pending "
                    "or scheduled plan change"
                ),
                "plan_change_id": existing_change.id,
                "status": existing_change.status,
            },
        )

    price_difference = round(
        float(new_plan.price) - float(current_plan.price),
        2,
    )

    # Upgrade: requires payment of the positive difference.
    if price_difference > 0:
        plan_change = SubscriptionPlanChange(
            subscription_id=subscription.id,
            user_id=subscription.user_id,
            old_plan_id=current_plan.id,
            new_plan_id=new_plan.id,
            change_type=PlanChangeType.UPGRADE.value,
            status=PlanChangeStatus.PENDING_PAYMENT.value,
            old_amount=float(current_plan.price),
            new_amount=float(new_plan.price),
            amount_difference=price_difference,
            effective_at=None,
        )

        db.add(plan_change)
        db.commit()
        db.refresh(plan_change)

        return ChangePlanResult(
            message=(
                "Upgrade created. Complete payment of the "
                "price difference to activate the new plan."
            ),
            plan_change=plan_change,
            requires_payment=True,
            amount_due=price_difference,
        )

    # Downgrade: schedule for the current subscription end date.
    plan_change = SubscriptionPlanChange(
        subscription_id=subscription.id,
        user_id=subscription.user_id,
        old_plan_id=current_plan.id,
        new_plan_id=new_plan.id,
        change_type=PlanChangeType.DOWNGRADE.value,
        status=PlanChangeStatus.SCHEDULED.value,
        old_amount=float(current_plan.price),
        new_amount=float(new_plan.price),
        amount_difference=0,
        effective_at=subscription.end_date,
    )

    subscription.pending_plan_id = new_plan.id
    subscription.plan_change_effective_at = (
        subscription.end_date
    )

    db.add(plan_change)
    db.commit()
    db.refresh(plan_change)

    return ChangePlanResult(
        message=(
            "Downgrade scheduled. It will be applied "
            "at the end of the current subscription."
        ),
        plan_change=plan_change,
        requires_payment=False,
        amount_due=0,
    )


@router.get(
    "/{subscription_id}/plan-changes",
    response_model=list[PlanChangeResponse],
)
def list_plan_changes(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = get_subscription_or_404(
        db,
        subscription_id,
    )

    ensure_subscription_access(
        subscription,
        current_user,
    )

    return (
        db.query(SubscriptionPlanChange)
        .filter(
            SubscriptionPlanChange.subscription_id
            == subscription.id
        )
        .order_by(SubscriptionPlanChange.id.desc())
        .all()
    )


@router.post(
    "/{subscription_id}/plan-changes/{change_id}/cancel",
    response_model=PlanChangeResponse,
)
def cancel_plan_change(
    subscription_id: int,
    change_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = get_subscription_or_404(
        db,
        subscription_id,
    )

    ensure_subscription_access(
        subscription,
        current_user,
    )

    plan_change = (
        db.query(SubscriptionPlanChange)
        .filter(
            SubscriptionPlanChange.id == change_id,
            SubscriptionPlanChange.subscription_id
            == subscription.id,
        )
        .first()
    )

    if not plan_change:
        raise HTTPException(
            status_code=404,
            detail="Plan change not found",
        )

    if plan_change.status not in {
        PlanChangeStatus.PENDING_PAYMENT.value,
        PlanChangeStatus.SCHEDULED.value,
    }:
        raise HTTPException(
            status_code=400,
            detail="This plan change cannot be cancelled",
        )

    plan_change.status = PlanChangeStatus.CANCELLED.value
    plan_change.cancelled_at = datetime.utcnow()

    if subscription.pending_plan_id == plan_change.new_plan_id:
        subscription.pending_plan_id = None
        subscription.plan_change_effective_at = None

    db.commit()
    db.refresh(plan_change)

    return plan_change


# =========================================================
# PROCESS SCHEDULED DOWNGRADES
# Admin endpoint for now. Later run it using a cron job.
# =========================================================

@router.post("/process-scheduled-plan-changes")
def process_scheduled_plan_changes(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    now = datetime.utcnow()

    changes = (
        db.query(SubscriptionPlanChange)
        .filter(
            SubscriptionPlanChange.status
            == PlanChangeStatus.SCHEDULED.value,
            SubscriptionPlanChange.effective_at.isnot(None),
            SubscriptionPlanChange.effective_at <= now,
        )
        .all()
    )

    processed = []

    for change in changes:
        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.id == change.subscription_id
            )
            .first()
        )

        new_plan = (
            db.query(MealPlan)
            .filter(MealPlan.id == change.new_plan_id)
            .first()
        )

        if not subscription or not new_plan:
            change.status = PlanChangeStatus.FAILED.value
            continue

        subscription.plan_id = new_plan.id
        subscription.amount = float(new_plan.price)
        subscription.pending_plan_id = None
        subscription.plan_change_effective_at = None

        change.status = PlanChangeStatus.COMPLETED.value
        change.completed_at = now

        processed.append(change.id)

    db.commit()

    return {
        "message": "Scheduled plan changes processed",
        "processed_count": len(processed),
        "processed_ids": processed,
    }


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
)
def get_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = get_subscription_or_404(
        db,
        subscription_id,
    )

    ensure_subscription_access(
        subscription,
        current_user,
    )

    return subscription


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
    subscription = get_subscription_or_404(
        db,
        subscription_id,
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


@router.post(
    "/{subscription_id}/cancel",
    response_model=SubscriptionResponse,
)
def cancel_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = get_subscription_or_404(
        db,
        subscription_id,
    )

    ensure_subscription_access(
        subscription,
        current_user,
    )

    if subscription.status == SubscriptionStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail="Subscription is already cancelled",
        )

    active_pause = get_active_pause(
        db,
        subscription.id,
    )

    if active_pause:
        active_pause.resumed_at = datetime.utcnow()
        active_pause.duration_seconds = int(
            (
                active_pause.resumed_at
                - active_pause.paused_at
            ).total_seconds()
        )

    subscription.status = SubscriptionStatus.CANCELLED
    subscription.paused_at = None
    subscription.cancelled_at = datetime.utcnow()

    db.commit()
    db.refresh(subscription)

    return subscription