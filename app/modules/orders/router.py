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
from app.modules.subscriptions.models import Subscription, SubscriptionStatus, PaymentStatus
from app.modules.users.models import User, UserRole
from app.modules.payments.models import Payment
from app.modules.deliveries.models import Delivery


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

    if subscription.status != SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail="Cannot create order because subscription is not active",
        )

    if subscription.payment_status != PaymentStatus.PAID:
        raise HTTPException(
            status_code=400,
            detail="Cannot create order before subscription payment is completed",
        )

    plan = db.query(MealPlan).filter(MealPlan.id == subscription.plan_id).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    existing_order = (
        db.query(Order)
        .filter(
            Order.subscription_id == subscription.id,
            Order.status.notin_([
                OrderStatus.CANCELLED,
                OrderStatus.DELIVERED,
            ]),
        )
        .first()
    )

    if existing_order:
        raise HTTPException(
            status_code=400,
            detail="This subscription already has an active order",
        )

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
                "payment_status": subscription.payment_status.value,
                "subscription_status": subscription.status.value,
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

    results = []

    for order in orders:
        user = db.query(User).filter(User.id == order.user_id).first()

        subscription = (
            db.query(Subscription)
            .filter(Subscription.id == order.subscription_id)
            .first()
        )

        plan = None
        if subscription:
            plan = db.query(MealPlan).filter(MealPlan.id == subscription.plan_id).first()

        payment = (
            db.query(Payment)
            .filter(Payment.subscription_id == order.subscription_id)
            .order_by(Payment.id.desc())
            .first()
        )

        delivery = (
            db.query(Delivery)
            .filter(Delivery.order_id == order.id)
            .order_by(Delivery.id.desc())
            .first()
        )

        driver = None
        if delivery and delivery.driver_id:
            driver = db.query(User).filter(User.id == delivery.driver_id).first()

        payment_status = None
        if payment:
            payment_status = payment.status
        elif subscription:
            payment_status = (
                subscription.payment_status.value
                if hasattr(subscription.payment_status, "value")
                else subscription.payment_status
            )

        results.append(
            {
                "id": order.id,
                "order_number": order.order_number,
                "order_status": order.status.value if hasattr(order.status, "value") else order.status,
                "total_amount": order.total_amount,
                "delivery_date": order.delivery_date,
                "delivery_address": order.delivery_address,
                "delivery_notes": order.delivery_notes,
                "items": order.items,
                "created_at": order.created_at,

                "customer": {
                    "id": user.id if user else None,
                    "first_name": user.first_name if user else None,
                    "last_name": user.last_name if user else None,
                    "full_name": f"{user.first_name} {user.last_name}" if user else None,
                    "email": user.email if user else None,
                    "phone": user.phone if user else None,
                },

                "subscription": {
                    "id": subscription.id if subscription else None,
                    "status": (
                        subscription.status.value
                        if subscription and hasattr(subscription.status, "value")
                        else subscription.status if subscription else None
                    ),
                    "payment_status": (
                        subscription.payment_status.value
                        if subscription and hasattr(subscription.payment_status, "value")
                        else subscription.payment_status if subscription else None
                    ),
                    "amount": subscription.amount if subscription else None,
                    "start_date": subscription.start_date if subscription else None,
                    "end_date": subscription.end_date if subscription else None,
                },

                "plan": {
                    "id": plan.id if plan else None,
                    "name": plan.name_en if plan else None,
                    "name_en": plan.name_en if plan else None,
                    "name_ar": plan.name_ar if plan else None,
                    "plan_type": (
                        plan.plan_type.value
                        if plan and hasattr(plan.plan_type, "value")
                        else plan.plan_type if plan else None
                    ),
                    "goal": (
                        plan.goal.value
                        if plan and hasattr(plan.goal, "value")
                        else plan.goal if plan else None
                    ),
                    "duration_days": plan.duration_days if plan else None,
                    "meals_per_day": plan.meals_per_day if plan else None,
                    "total_meals": plan.total_meals if plan else None,
                },

                "payment": {
                    "id": payment.id if payment else None,
                    "status": payment_status,
                    "provider": payment.provider if payment else None,
                    "amount": payment.amount if payment else order.total_amount,
                    "currency": payment.currency if payment else "usd",
                    "paid_at": payment.paid_at if payment else None,
                    "stripe_payment_intent_id": (
                        payment.stripe_payment_intent_id if payment else None
                    ),
                },

                "delivery": {
                    "id": delivery.id if delivery else None,
                    "status": (
                        delivery.status.value
                        if delivery and hasattr(delivery.status, "value")
                        else delivery.status if delivery else None
                    ),
                    "scheduled_at": delivery.scheduled_at if delivery else None,
                    "picked_up_at": delivery.picked_up_at if delivery else None,
                    "delivered_at": delivery.delivered_at if delivery else None,
                    "current_latitude": delivery.current_latitude if delivery else None,
                    "current_longitude": delivery.current_longitude if delivery else None,
                },

                "driver": {
                    "id": driver.id if driver else None,
                    "first_name": driver.first_name if driver else None,
                    "last_name": driver.last_name if driver else None,
                    "full_name": f"{driver.first_name} {driver.last_name}" if driver else None,
                    "email": driver.email if driver else None,
                    "phone": driver.phone if driver else None,
                } if driver else None,
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