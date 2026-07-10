from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.deliveries.models import Delivery, DeliveryStatus
from app.modules.meals.models import Meal, MealCategory
from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import Payment, PaymentRecordStatus
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import (
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


DASHBOARD_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.FINANCE_MANAGER,
    UserRole.DELIVERY_MANAGER,
    UserRole.NUTRITION_MANAGER,
)


def enum_value(value):
    """
    Safely return the string value of either a Python Enum or a string.
    """
    if value is None:
        return None

    return value.value if hasattr(value, "value") else value


@router.get("/admin")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*DASHBOARD_ROLES)),
):
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    tomorrow_start = today_start + timedelta(days=1)
    month_start = datetime(now.year, now.month, 1)

    total_users = db.query(func.count(User.id)).scalar() or 0

    total_customers = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.CUSTOMER)
        .scalar()
        or 0
    )

    total_drivers = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.DRIVER)
        .scalar()
        or 0
    )

    active_drivers = (
        db.query(func.count(User.id))
        .filter(
            User.role == UserRole.DRIVER,
            User.is_active.is_(True),
        )
        .scalar()
        or 0
    )

    new_users_today = (
        db.query(func.count(User.id))
        .filter(
            User.created_at >= today_start,
            User.created_at < tomorrow_start,
        )
        .scalar()
        or 0
    )

    total_subscriptions = db.query(func.count(Subscription.id)).scalar() or 0

    active_subscriptions = (
        db.query(func.count(Subscription.id))
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
        .scalar()
        or 0
    )

    pending_subscriptions = (
        db.query(func.count(Subscription.id))
        .filter(Subscription.status == SubscriptionStatus.PENDING_PAYMENT)
        .scalar()
        or 0
    )

    paused_subscriptions = (
        db.query(func.count(Subscription.id))
        .filter(Subscription.status == SubscriptionStatus.PAUSED)
        .scalar()
        or 0
    )

    cancelled_subscriptions = (
        db.query(func.count(Subscription.id))
        .filter(Subscription.status == SubscriptionStatus.CANCELLED)
        .scalar()
        or 0
    )

    paid_subscriptions = (
        db.query(func.count(Subscription.id))
        .filter(Subscription.payment_status == PaymentStatus.PAID)
        .scalar()
        or 0
    )

    unpaid_subscriptions = (
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.payment_status.in_(
                [
                    PaymentStatus.UNPAID,
                    PaymentStatus.PENDING,
                ]
            )
        )
        .scalar()
        or 0
    )

    total_payments = db.query(func.count(Payment.id)).scalar() or 0

    successful_payments = (
        db.query(func.count(Payment.id))
        .filter(Payment.status == PaymentRecordStatus.PAID.value)
        .scalar()
        or 0
    )

    pending_payments = (
        db.query(func.count(Payment.id))
        .filter(Payment.status == PaymentRecordStatus.PENDING.value)
        .scalar()
        or 0
    )

    failed_payments = (
        db.query(func.count(Payment.id))
        .filter(Payment.status == PaymentRecordStatus.FAILED.value)
        .scalar()
        or 0
    )

    total_revenue = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.status == PaymentRecordStatus.PAID.value)
        .scalar()
        or 0
    )

    today_revenue = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.status == PaymentRecordStatus.PAID.value,
            Payment.paid_at >= today_start,
            Payment.paid_at < tomorrow_start,
        )
        .scalar()
        or 0
    )

    monthly_revenue = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.status == PaymentRecordStatus.PAID.value,
            Payment.paid_at >= month_start,
        )
        .scalar()
        or 0
    )

    total_orders = db.query(func.count(Order.id)).scalar() or 0

    today_orders = (
        db.query(func.count(Order.id))
        .filter(
            Order.created_at >= today_start,
            Order.created_at < tomorrow_start,
        )
        .scalar()
        or 0
    )

    pending_orders = (
        db.query(func.count(Order.id))
        .filter(Order.status == OrderStatus.PENDING)
        .scalar()
        or 0
    )

    delivered_orders = (
        db.query(func.count(Order.id))
        .filter(Order.status == OrderStatus.DELIVERED)
        .scalar()
        or 0
    )

    cancelled_orders = (
        db.query(func.count(Order.id))
        .filter(Order.status == OrderStatus.CANCELLED)
        .scalar()
        or 0
    )

    out_for_delivery_orders = (
        db.query(func.count(Order.id))
        .filter(Order.status == OrderStatus.OUT_FOR_DELIVERY)
        .scalar()
        or 0
    )

    total_deliveries = db.query(func.count(Delivery.id)).scalar() or 0

    pending_deliveries = (
        db.query(func.count(Delivery.id))
        .filter(Delivery.status == DeliveryStatus.PENDING)
        .scalar()
        or 0
    )

    assigned_deliveries = (
        db.query(func.count(Delivery.id))
        .filter(Delivery.status == DeliveryStatus.ASSIGNED)
        .scalar()
        or 0
    )

    active_deliveries = (
        db.query(func.count(Delivery.id))
        .filter(
            Delivery.status.in_(
                [
                    DeliveryStatus.PICKED_UP,
                    DeliveryStatus.OUT_FOR_DELIVERY,
                ]
            )
        )
        .scalar()
        or 0
    )

    delivered_deliveries = (
        db.query(func.count(Delivery.id))
        .filter(Delivery.status == DeliveryStatus.DELIVERED)
        .scalar()
        or 0
    )

    failed_deliveries = (
        db.query(func.count(Delivery.id))
        .filter(Delivery.status == DeliveryStatus.FAILED)
        .scalar()
        or 0
    )

    unassigned_deliveries = (
        db.query(func.count(Delivery.id))
        .filter(Delivery.driver_id.is_(None))
        .scalar()
        or 0
    )

    total_categories = db.query(func.count(MealCategory.id)).scalar() or 0
    total_meals = db.query(func.count(Meal.id)).scalar() or 0

    available_meals = (
        db.query(func.count(Meal.id))
        .filter(Meal.is_available.is_(True))
        .scalar()
        or 0
    )

    unavailable_meals = (
        db.query(func.count(Meal.id))
        .filter(Meal.is_available.is_(False))
        .scalar()
        or 0
    )

    total_plans = db.query(func.count(MealPlan.id)).scalar() or 0

    active_plans = (
        db.query(func.count(MealPlan.id))
        .filter(MealPlan.is_active.is_(True))
        .scalar()
        or 0
    )

    inactive_plans = (
        db.query(func.count(MealPlan.id))
        .filter(MealPlan.is_active.is_(False))
        .scalar()
        or 0
    )

    recent_payment_rows = (
        db.query(Payment, User, Subscription, MealPlan)
        .outerjoin(User, User.id == Payment.user_id)
        .outerjoin(
            Subscription,
            Subscription.id == Payment.subscription_id,
        )
        .outerjoin(
            MealPlan,
            MealPlan.id == Subscription.plan_id,
        )
        .order_by(Payment.id.desc())
        .limit(5)
        .all()
    )

    recent_payments = []

    for payment, user, subscription, plan in recent_payment_rows:
        recent_payments.append(
            {
                "id": payment.id,
                "customer": {
                    "id": user.id if user else None,
                    "full_name": (
                        f"{user.first_name} {user.last_name}"
                        if user
                        else None
                    ),
                    "email": user.email if user else None,
                    "phone": user.phone if user else None,
                },
                "subscription": {
                    "id": subscription.id if subscription else None,
                    "plan_name": plan.name_en if plan else None,
                },
                "provider": payment.provider,
                "status": payment.status,
                "amount": payment.amount,
                "currency": payment.currency,
                "paid_at": payment.paid_at,
                "created_at": payment.created_at,
            }
        )

    recent_order_rows = (
        db.query(Order, User, Subscription, MealPlan)
        .outerjoin(User, User.id == Order.user_id)
        .outerjoin(
            Subscription,
            Subscription.id == Order.subscription_id,
        )
        .outerjoin(
            MealPlan,
            MealPlan.id == Order.plan_id,
        )
        .order_by(Order.id.desc())
        .limit(5)
        .all()
    )

    recent_orders = []

    for order, user, subscription, plan in recent_order_rows:
        payment = (
            db.query(Payment)
            .filter(Payment.subscription_id == order.subscription_id)
            .order_by(Payment.id.desc())
            .first()
        )

        recent_orders.append(
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer": {
                    "id": user.id if user else None,
                    "full_name": (
                        f"{user.first_name} {user.last_name}"
                        if user
                        else None
                    ),
                    "email": user.email if user else None,
                },
                "plan": {
                    "id": plan.id if plan else None,
                    "name": plan.name_en if plan else None,
                },
                "subscription": {
                    "id": subscription.id if subscription else None,
                    "status": (
                        enum_value(subscription.status)
                        if subscription
                        else None
                    ),
                    "payment_status": (
                        enum_value(subscription.payment_status)
                        if subscription
                        else None
                    ),
                },
                "payment": {
                    "id": payment.id if payment else None,
                    "status": payment.status if payment else None,
                    "provider": payment.provider if payment else None,
                },
                "order_status": enum_value(order.status),
                "amount": order.total_amount,
                "delivery_date": order.delivery_date,
                "created_at": order.created_at,
            }
        )

    recent_subscription_rows = (
        db.query(Subscription, User, MealPlan)
        .outerjoin(User, User.id == Subscription.user_id)
        .outerjoin(MealPlan, MealPlan.id == Subscription.plan_id)
        .order_by(Subscription.id.desc())
        .limit(5)
        .all()
    )

    recent_subscriptions = []

    for subscription, user, plan in recent_subscription_rows:
        recent_subscriptions.append(
            {
                "id": subscription.id,
                "customer": {
                    "id": user.id if user else None,
                    "full_name": (
                        f"{user.first_name} {user.last_name}"
                        if user
                        else None
                    ),
                    "email": user.email if user else None,
                    "phone": user.phone if user else None,
                },
                "plan": {
                    "id": plan.id if plan else None,
                    "name": plan.name_en if plan else None,
                },
                "status": enum_value(subscription.status),
                "payment_status": enum_value(
                    subscription.payment_status
                ),
                "amount": subscription.amount,
                "start_date": subscription.start_date,
                "end_date": subscription.end_date,
                "created_at": subscription.created_at,
            }
        )

    popular_plan_rows = (
        db.query(
            MealPlan.id,
            MealPlan.name_en,
            MealPlan.price,
            func.count(Subscription.id).label("subscription_count"),
        )
        .outerjoin(
            Subscription,
            Subscription.plan_id == MealPlan.id,
        )
        .group_by(
            MealPlan.id,
            MealPlan.name_en,
            MealPlan.price,
        )
        .order_by(func.count(Subscription.id).desc())
        .limit(5)
        .all()
    )

    popular_plans = [
        {
            "id": row.id,
            "name": row.name_en,
            "price": row.price,
            "subscription_count": row.subscription_count,
        }
        for row in popular_plan_rows
    ]
    
    return {
        "generated_at": now,

        "summary": {
            "total_revenue": float(total_revenue),
            "today_revenue": float(today_revenue),
            "monthly_revenue": float(monthly_revenue),
            "total_customers": total_customers,
            "active_subscriptions": active_subscriptions,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "active_deliveries": active_deliveries,
        },

        "users": {
            "total": total_users,
            "customers": total_customers,
            "drivers": total_drivers,
            "active_drivers": active_drivers,
            "new_today": new_users_today,
        },

        "subscriptions": {
            "total": total_subscriptions,
            "active": active_subscriptions,
            "pending_payment": pending_subscriptions,
            "paused": paused_subscriptions,
            "cancelled": cancelled_subscriptions,
            "paid": paid_subscriptions,
            "unpaid_or_pending": unpaid_subscriptions,
        },

        "payments": {
            "total": total_payments,
            "successful": successful_payments,
            "pending": pending_payments,
            "failed": failed_payments,
            "revenue": {
                "total": float(total_revenue),
                "today": float(today_revenue),
                "this_month": float(monthly_revenue),
            },
        },

        "orders": {
            "total": total_orders,
            "today": today_orders,
            "pending": pending_orders,
            "out_for_delivery": out_for_delivery_orders,
            "delivered": delivered_orders,
            "cancelled": cancelled_orders,
        },

        "deliveries": {
            "total": total_deliveries,
            "pending": pending_deliveries,
            "assigned": assigned_deliveries,
            "active": active_deliveries,
            "delivered": delivered_deliveries,
            "failed": failed_deliveries,
            "unassigned": unassigned_deliveries,
        },

        "catalog": {
            "categories": total_categories,
            "meals": {
                "total": total_meals,
                "available": available_meals,
                "unavailable": unavailable_meals,
            },
            "plans": {
                "total": total_plans,
                "active": active_plans,
                "inactive": inactive_plans,
            },
        },

        "recent_activity": {
            "payments": recent_payments,
            "orders": recent_orders,
            "subscriptions": recent_subscriptions,
        },

        "popular_plans": popular_plans,
    }
