from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.users.models import User, UserRole
from app.modules.users.models import User as UserModel
from app.modules.orders.models import Order
from app.modules.deliveries.models import Delivery
from app.modules.subscriptions.models import Subscription, PaymentStatus


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