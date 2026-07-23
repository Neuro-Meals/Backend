from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.users.models import User, UserRole
from app.modules.users.models import User as UserModel
from app.modules.orders.models import Order
from app.modules.deliveries.models import Delivery
from app.modules.subscriptions.models import Subscription, PaymentStatus
from app.modules.subscriptions.models import SubscriptionStatus
from app.modules.payments.models import Payment, PaymentRecordStatus
from app.modules.meals.models import Meal


router = APIRouter(prefix="/reports", tags=["Reports"])


REPORT_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.FINANCE_MANAGER,
)


@router.get("/summary")
def summary_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REPORT_ROLES)),
):
    total_users = db.query(UserModel).count()
    total_orders = db.query(Order).count()
    total_subscriptions = db.query(Subscription).count()
    total_deliveries = db.query(Delivery).count()

    paid_revenue = (
        db.query(func.coalesce(func.sum(Subscription.amount), 0))
        .filter(Subscription.payment_status == PaymentStatus.PAID)
        .scalar()
    )

    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "total_subscriptions": total_subscriptions,
        "total_deliveries": total_deliveries,
        "paid_revenue": float(paid_revenue),
    }


@router.get("/orders")
def orders_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REPORT_ROLES)),
):
    rows = (
        db.query(Order.status, func.count(Order.id))
        .group_by(Order.status)
        .all()
    )

    return {
        "orders_by_status": [
            {"status": status.value if hasattr(status, "value") else str(status), "count": count}
            for status, count in rows
        ]
    }


@router.get("/subscriptions")
def subscriptions_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REPORT_ROLES)),
):
    rows = (
        db.query(Subscription.status, func.count(Subscription.id))
        .group_by(Subscription.status)
        .all()
    )

    return {
        "subscriptions_by_status": [
            {"status": status.value if hasattr(status, "value") else str(status), "count": count}
            for status, count in rows
        ]
    }


@router.get("/deliveries")
def deliveries_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REPORT_ROLES)),
):
    rows = (
        db.query(Delivery.status, func.count(Delivery.id))
        .group_by(Delivery.status)
        .all()
    )

    return {
        "deliveries_by_status": [
            {"status": status.value if hasattr(status, "value") else str(status), "count": count}
            for status, count in rows
        ]
    }


@router.get("/revenue")
def revenue_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REPORT_ROLES)),
):
    paid = (
        db.query(func.coalesce(func.sum(Subscription.amount), 0))
        .filter(Subscription.payment_status == PaymentStatus.PAID)
        .scalar()
    )

    unpaid = (
        db.query(func.coalesce(func.sum(Subscription.amount), 0))
        .filter(Subscription.payment_status != PaymentStatus.PAID)
        .scalar()
    )

    return {
        "paid_revenue": float(paid),
        "unpaid_or_pending_amount": float(unpaid),
    }


@router.get("/dashboard")
def dashboard_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REPORT_ROLES)),
):
    today = datetime.utcnow().date()
    this_month = today.strftime("%Y-%m")
    last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    week_ago = today - timedelta(days=7)

    # ─── User counts ───
    total_users = db.query(UserModel).count()
    total_customers = (
        db.query(UserModel)
        .filter(UserModel.role == UserRole.CUSTOMER)
        .count()
    )
    total_drivers = (
        db.query(UserModel)
        .filter(UserModel.role == UserRole.DRIVER)
        .count()
    )
    new_users_this_week = (
        db.query(UserModel)
        .filter(UserModel.created_at >= week_ago)
        .count()
    )

    # ─── Order counts ───
    total_orders = db.query(Order).count()
    orders_today = (
        db.query(Order)
        .filter(func.date(Order.created_at) == today)
        .count()
    )

    # Orders by status
    order_status_rows = (
        db.query(Order.status, func.count(Order.id))
        .group_by(Order.status)
        .all()
    )
    orders_by_status = {
        (s.value if hasattr(s, "value") else str(s)): c
        for s, c in order_status_rows
    }

    # ─── Delivery counts ───
    total_deliveries = db.query(Delivery).count()
    deliveries_today = (
        db.query(Delivery)
        .filter(func.date(Delivery.created_at) == today)
        .count()
    )

    delivery_status_rows = (
        db.query(Delivery.status, func.count(Delivery.id))
        .group_by(Delivery.status)
        .all()
    )
    deliveries_by_status = {
        (s.value if hasattr(s, "value") else str(s)): c
        for s, c in delivery_status_rows
    }

    # ─── Subscription counts ───
    total_subscriptions = db.query(Subscription).count()
    active_subscriptions = (
        db.query(Subscription)
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
        .count()
    )

    sub_status_rows = (
        db.query(Subscription.status, func.count(Subscription.id))
        .group_by(Subscription.status)
        .all()
    )
    subscriptions_by_status = {
        (s.value if hasattr(s, "value") else str(s)): c
        for s, c in sub_status_rows
    }

    # ─── Revenue from payments ───
    paid_revenue = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.status == PaymentRecordStatus.PAID.value)
        .scalar()
    )

    # Monthly revenue (this month vs last month) from payments
    monthly_revenue = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.status == PaymentRecordStatus.PAID.value)
        .filter(Payment.paid_at.isnot(None))
        .filter(func.to_char(Payment.paid_at, "YYYY-MM") == this_month)
        .scalar()
    )
    last_month_revenue = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.status == PaymentRecordStatus.PAID.value)
        .filter(Payment.paid_at.isnot(None))
        .filter(func.to_char(Payment.paid_at, "YYYY-MM") == last_month)
        .scalar()
    )

    # ─── Payment counts by status ───
    payment_status_rows = (
        db.query(Payment.status, func.count(Payment.id))
        .group_by(Payment.status)
        .all()
    )
    payment_counts = {}
    for s, c in payment_status_rows:
        key = s if isinstance(s, str) else (s.value if hasattr(s, "value") else str(s))
        payment_counts[key] = c

    total_payments = sum(payment_counts.values())
    completed_payments = payment_counts.get("paid", 0)
    pending_payments = payment_counts.get("pending", 0)
    success_rate = (
        round((completed_payments / total_payments) * 100, 1)
        if total_payments > 0
        else 0
    )
    claim_count = (
        payment_counts.get("refunded", 0)
        + payment_counts.get("failed", 0)
        + payment_counts.get("cancelled", 0)
    )
    claim_rate = (
        round((claim_count / total_payments) * 100, 1)
        if total_payments > 0
        else 0
    )

    # ─── Meals count ───
    total_meals = db.query(Meal).count()

    # ─── Growth percentages ───
    rev_growth = (
        round(
            (float(monthly_revenue) - float(last_month_revenue))
            / float(last_month_revenue)
            * 100,
            1,
        )
        if float(last_month_revenue) > 0
        else 0
    )

    sub_growth = 0
    if active_subscriptions > 0 and total_subscriptions > active_subscriptions:
        non_active = total_subscriptions - active_subscriptions
        sub_growth = round(
            (active_subscriptions - non_active) / max(non_active, 1) * 100, 1
        )

    # ─── Avg order value ───
    avg_order_value = (
        round(float(paid_revenue) / total_orders, 2)
        if total_orders > 0
        else 0
    )

    # ─── Retention & churn ───
    active = subscriptions_by_status.get("active", 0)
    cancelled = subscriptions_by_status.get("cancelled", 0)
    expired = subscriptions_by_status.get("expired", 0)
    paused = subscriptions_by_status.get("paused", 0)
    total_engaged = active + cancelled + expired + paused
    churn_rate = (
        round(((cancelled + expired) / total_engaged) * 100, 1)
        if total_engaged > 0
        else 0
    )
    retention_rate = (
        round((active / total_engaged) * 100, 1)
        if total_engaged > 0
        else 0
    )

    return {
        "total_users": total_users,
        "total_customers": total_customers,
        "total_drivers": total_drivers,
        "new_users_this_week": new_users_this_week,
        "total_orders": total_orders,
        "orders_today": orders_today,
        "orders_by_status": orders_by_status,
        "total_deliveries": total_deliveries,
        "deliveries_today": deliveries_today,
        "deliveries_by_status": deliveries_by_status,
        "total_subscriptions": total_subscriptions,
        "active_subscriptions": active_subscriptions,
        "subscriptions_by_status": subscriptions_by_status,
        "paid_revenue": float(paid_revenue),
        "monthly_revenue": float(monthly_revenue),
        "last_month_revenue": float(last_month_revenue),
        "payment_counts": payment_counts,
        "total_payments": total_payments,
        "completed_payments": completed_payments,
        "pending_payments": pending_payments,
        "success_rate": success_rate,
        "claim_rate": claim_rate,
        "total_meals": total_meals,
        "rev_growth": rev_growth,
        "sub_growth": sub_growth,
        "avg_order_value": avg_order_value,
        "churn_rate": churn_rate,
        "retention_rate": retention_rate,
    }