from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

def _enum(value):
    if value is None:
        return None

    if isinstance(value, Enum):
        return value.value

    return value


def _datetime(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    return value


def _decimal(value):
    if value is None:
        return None

    if isinstance(value, Decimal):
        return float(value)

    return value


def _fullname(user):
    if user is None:
        return None

    first = getattr(user, "first_name", "") or ""
    last = getattr(user, "last_name", "") or ""

    return f"{first} {last}".strip()

def build_user_summary(user):
    if user is None:
        return None

    return {
        "id": user.id,
        "name": _fullname(user),
        "first_name": getattr(user, "first_name", None),
        "last_name": getattr(user, "last_name", None),
        "email": getattr(user, "email", None),
        "phone": getattr(user, "phone", None),
        "role": _enum(getattr(user, "role", None)),
        "status": _enum(getattr(user, "status", None)),
        "is_verified": getattr(user, "is_verified", None),
    }

def build_customer_summary(customer):
    if customer is None:
        return None

    return build_user_summary(customer)

def build_driver_summary(driver):
    if driver is None:
        return None

    return {
        "id": driver.id,
        "name": _fullname(driver),
        "phone": getattr(driver, "phone", None),
        "email": getattr(driver, "email", None),
        "status": _enum(getattr(driver, "status", None)),
        "is_active": getattr(driver, "is_active", None),
    }

def build_meal_summary(meal):
    if meal is None:
        return None

    return {
        "id": meal.id,
        "name_en": getattr(meal, "name_en", None),
        "name_ar": getattr(meal, "name_ar", None),
        "category_id": getattr(meal, "category_id", None),
        "price": _decimal(getattr(meal, "price", None)),
        "calories": getattr(meal, "calories", None),
        "protein": getattr(meal, "protein", None),
        "carbs": getattr(meal, "carbs", None),
        "fat": getattr(meal, "fat", None),
        "is_active": getattr(meal, "is_active", None),
    }

def build_plan_summary(plan):
    if plan is None:
        return None

    return {
        "id": plan.id,
        "name": getattr(plan, "name", None),
        "price": _decimal(getattr(plan, "price", None)),
        "duration_days": getattr(plan, "duration_days", None),
    }

def build_subscription_summary(subscription):
    if subscription is None:
        return None

    return {
        "id": subscription.id,
        "status": _enum(getattr(subscription, "status", None)),
        "start_date": _datetime(getattr(subscription, "start_date", None)),
        "end_date": _datetime(getattr(subscription, "end_date", None)),
        "created_at": _datetime(getattr(subscription, "created_at", None)),
    }


def build_order_summary(order):
    if order is None:
        return None

    return {
        "id": order.id,
        "order_number": getattr(order, "order_number", None),
        "status": _enum(getattr(order, "status", None)),
        "total_amount": _decimal(
            getattr(order, "total_amount", None)
        ),
        "created_at": _datetime(
            getattr(order, "created_at", None)
        ),
    }

def build_delivery_summary(delivery):
    if delivery is None:
        return None

    return {
        "id": delivery.id,
        "status": _enum(delivery.status),
        "order_id": delivery.order_id,
        "customer_id": delivery.user_id,
        "driver_id": delivery.driver_id,
        "scheduled_at": _datetime(
            delivery.scheduled_at
        ),
        "picked_up_at": _datetime(
            delivery.picked_up_at
        ),
        "delivered_at": _datetime(
            delivery.delivered_at
        ),
        "created_at": _datetime(
            delivery.created_at
        ),
    }

def build_delivery_timeline(delivery):
    if delivery is None:
        return None

    return {
        "created_at": _datetime(
            delivery.created_at
        ),
        "scheduled_at": _datetime(
            delivery.scheduled_at
        ),
        "picked_up_at": _datetime(
            delivery.picked_up_at
        ),
        "delivered_at": _datetime(
            delivery.delivered_at
        ),
        "updated_at": _datetime(
            delivery.updated_at
        ),
    }

def build_delivery_details(
    delivery,
    customer=None,
    driver=None,
    order=None,
):
    return {
        "delivery": build_delivery_summary(delivery),
        "customer": build_customer_summary(customer),
        "driver": build_driver_summary(driver),
        "order": build_order_summary(order),
        "timeline": build_delivery_timeline(delivery),
    }
    