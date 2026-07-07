from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.orders.models import Order, OrderStatus
from app.modules.orders.schemas import (
    OrderFromSubscriptionCreate,
    OrderResponse,
    OrderStatusUpdate,
)
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import Subscription, SubscriptionStatus
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/orders", tags=["Orders"])


def generate_order_number() -> str:
    return f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


@router.post("/from-subscription", response_model=OrderResponse)
def create_order_from_subscription(
    payload: OrderFromSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = (
        db.query(Subscription)
        .filter(Subscription.id == payload.subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if current_user.role == UserRole.CUSTOMER and subscription.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    if subscription.status not in [
        SubscriptionStatus.PENDING_PAYMENT,
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAUSED,
    ]:
        raise HTTPException(
            status_code=400,
            detail="Cannot create order from this subscription status",
        )

    plan = db.query(MealPlan).filter(MealPlan.id == subscription.plan_id).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    order = Order(
        user_id=subscription.user_id,
        subscription_id=subscription.id,
        plan_id=subscription.plan_id,
        order_number=generate_order_number(),
        status=OrderStatus.PENDING,
        total_amount=subscription.amount,
        delivery_date=datetime.utcnow() + timedelta(days=1),
        delivery_address=payload.delivery_address or current_user.address,
        delivery_notes=payload.delivery_notes,
        items=[
            {
                "plan_id": plan.id,
                "plan_name": plan.name_en,
                "duration_days": plan.duration_days,
                "meals_per_day": plan.meals_per_day,
                "total_meals": plan.total_meals,
            }
        ],
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    return order


@router.get("/my", response_model=list[OrderResponse])
def my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .order_by(Order.id.desc())
        .all()
    )


@router.get("/")
def list_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
            UserRole.FINANCE_MANAGER,
        )
    ),
    search: str | None = Query(None),
    status: OrderStatus | None = Query(None),
    user_id: int | None = Query(None),
    subscription_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Order)

    if search:
        value = f"%{search}%"
        query = query.filter(
            or_(
                Order.order_number.ilike(value),
                Order.delivery_address.ilike(value),
            )
        )

    if status:
        query = query.filter(Order.status == status)

    if user_id:
        query = query.filter(Order.user_id == user_id)

    if subscription_id:
        query = query.filter(Order.subscription_id == subscription_id)

    total = query.count()

    orders = (
        query.order_by(Order.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": orders,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if current_user.role == UserRole.CUSTOMER and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = payload.status

    db.commit()
    db.refresh(order)

    return order


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if current_user.role == UserRole.CUSTOMER and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    if order.status in [OrderStatus.DELIVERED, OrderStatus.OUT_FOR_DELIVERY]:
        raise HTTPException(
            status_code=400,
            detail="Order cannot be cancelled at this stage",
        )

    order.status = OrderStatus.CANCELLED

    db.commit()
    db.refresh(order)

    return order