from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.common.exceptions import (
    BadRequestException,
    CustomerNotFoundException,
    ForbiddenException,
    OrderNotFoundException,
)
from app.common.responses import (
    dashboard_response,
    list_response,
    success_response,
    updated_response,
)
from app.db.database import get_db
from app.modules.auth.dependencies import (
    get_current_user,
    require_roles,
)
from app.modules.deliveries.models import Delivery
from app.modules.orders.models import (
    Order,
    OrderSource,
    OrderStatus,
)
from app.modules.payments.models import Payment
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import Subscription
from app.modules.users.models import (
    User,
    UserRole,
)


router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)


ORDER_MANAGEMENT_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.DELIVERY_MANAGER,
    UserRole.FINANCE_MANAGER,
    UserRole.NUTRITION_MANAGER,
)

def _enum_value(value: Any) -> Any:
    if value is None:
        return None

    return value.value if hasattr(value, "value") else value


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None

    first_name = getattr(user, "first_name", "") or ""
    last_name = getattr(user, "last_name", "") or ""

    return f"{first_name} {last_name}".strip()


def _get_order_or_404(
    db: Session,
    order_id: int,
) -> Order:
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if order is None:
        raise OrderNotFoundException()

    return order


def _is_management_user(user: User) -> bool:
    return user.role in set(ORDER_MANAGEMENT_ROLES)


def _ensure_order_access(
    order: Order,
    current_user: User,
) -> None:
    if _is_management_user(current_user):
        return

    if (
        current_user.role == UserRole.CUSTOMER
        and order.user_id == current_user.id
    ):
        return

    raise ForbiddenException(
        "You are not allowed to access this order."
    )


def _normalise_items(order: Order) -> list[dict[str, Any]]:
    raw_items = order.items or []

    if isinstance(raw_items, list):
        return [
            item
            for item in raw_items
            if isinstance(item, dict)
        ]

    if isinstance(raw_items, dict):
        nested_items = raw_items.get("items", [])

        if isinstance(nested_items, list):
            return [
                item
                for item in nested_items
                if isinstance(item, dict)
            ]

    return []


def _build_meal_statistics(
    order: Order,
) -> dict[str, Any]:
    items = _normalise_items(order)

    total_quantity = 0
    meal_names: list[str] = []
    delivery_locations: set[str] = set()

    for item in items:
        raw_quantity = item.get("quantity", 1)

        try:
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            quantity = 1

        quantity = max(quantity, 1)
        total_quantity += quantity

        meal_name = (
            item.get("meal_name")
            or item.get("name_en")
            or item.get("name")
        )

        if meal_name:
            meal_name = str(meal_name)

            if quantity > 1:
                meal_name = f"{meal_name} x{quantity}"

            meal_names.append(meal_name)

        delivery = item.get("delivery") or {}

        if isinstance(delivery, dict):
            location_key = (
                delivery.get("delivery_preference_id")
                or delivery.get("delivery_address")
                or delivery.get("place_name")
            )

            if location_key:
                delivery_locations.add(str(location_key))

    visible_meals = meal_names[:3]
    remaining_meals = len(meal_names) - len(visible_meals)

    meal_summary = ", ".join(visible_meals)

    if remaining_meals > 0:
        meal_summary = (
            f"{meal_summary} +{remaining_meals}"
        )

    return {
        "meal_item_count": len(items),
        "total_quantity": total_quantity,
        "meal_summary": meal_summary,
        "delivery_location_count": len(
            delivery_locations
        ),
    }

def _build_customer_summary(
    customer: User | None,
) -> dict[str, Any] | None:
    if customer is None:
        return None

    return {
        "id": customer.id,
        "first_name": getattr(
            customer,
            "first_name",
            None,
        ),
        "last_name": getattr(
            customer,
            "last_name",
            None,
        ),
        "full_name": _full_name(customer),
        "email": getattr(customer, "email", None),
        "phone": getattr(customer, "phone", None),
        "location": getattr(
            customer,
            "location",
            None,
        ),
        "address": getattr(
            customer,
            "address",
            None,
        ),
    }


def _build_subscription_summary(
    subscription: Subscription | None,
) -> dict[str, Any] | None:
    if subscription is None:
        return None

    return {
        "id": subscription.id,
        "user_id": getattr(
            subscription,
            "user_id",
            None,
        ),
        "plan_id": getattr(
            subscription,
            "plan_id",
            None,
        ),
        "status": _enum_value(
            getattr(subscription, "status", None)
        ),
        "payment_status": _enum_value(
            getattr(
                subscription,
                "payment_status",
                None,
            )
        ),
        "amount": getattr(
            subscription,
            "amount",
            None,
        ),
        "start_date": getattr(
            subscription,
            "start_date",
            None,
        ),
        "end_date": getattr(
            subscription,
            "end_date",
            None,
        ),
    }


def _build_plan_summary(
    plan: MealPlan | None,
) -> dict[str, Any] | None:
    if plan is None:
        return None

    return {
        "id": plan.id,
        "name": getattr(plan, "name_en", None),
        "name_en": getattr(
            plan,
            "name_en",
            None,
        ),
        "name_ar": getattr(
            plan,
            "name_ar",
            None,
        ),
        "plan_type": _enum_value(
            getattr(plan, "plan_type", None)
        ),
        "goal": _enum_value(
            getattr(plan, "goal", None)
        ),
        "duration_days": getattr(
            plan,
            "duration_days",
            None,
        ),
        "meals_per_day": getattr(
            plan,
            "meals_per_day",
            None,
        ),
        "total_meals": getattr(
            plan,
            "total_meals",
            None,
        ),
    }


def _build_payment_summary(
    payment: Payment | None,
    *,
    subscription: Subscription | None,
    order: Order,
) -> dict[str, Any] | None:
    if payment is None and subscription is None:
        return None

    payment_status = None

    if payment is not None:
        payment_status = _enum_value(
            getattr(payment, "status", None)
        )
    elif subscription is not None:
        payment_status = _enum_value(
            getattr(
                subscription,
                "payment_status",
                None,
            )
        )

    return {
        "id": (
            getattr(payment, "id", None)
            if payment
            else None
        ),
        "status": payment_status,
        "provider": (
            getattr(payment, "provider", None)
            if payment
            else None
        ),
        "amount": (
            getattr(payment, "amount", None)
            if payment
            else order.total_amount
        ),
        "currency": (
            getattr(payment, "currency", None)
            if payment
            else None
        ),
        "paid_at": (
            getattr(payment, "paid_at", None)
            if payment
            else None
        ),
        "provider_payment_id": (
            getattr(
                payment,
                "provider_payment_id",
                None,
            )
            if payment
            else None
        ),
    }


def _build_driver_summary(
    driver: User | None,
) -> dict[str, Any] | None:
    if driver is None:
        return None

    return {
        "id": driver.id,
        "first_name": getattr(
            driver,
            "first_name",
            None,
        ),
        "last_name": getattr(
            driver,
            "last_name",
            None,
        ),
        "full_name": _full_name(driver),
        "email": getattr(driver, "email", None),
        "phone": getattr(driver, "phone", None),
        "is_active": getattr(
            driver,
            "is_active",
            None,
        ),
    }


def _build_delivery_summary(
    delivery: Delivery | None,
) -> dict[str, Any] | None:
    if delivery is None:
        return None

    return {
        "id": delivery.id,
        "status": _enum_value(
            getattr(delivery, "status", None)
        ),
        "driver_id": getattr(
            delivery,
            "driver_id",
            None,
        ),
        "delivery_address": getattr(
            delivery,
            "delivery_address",
            None,
        ),
        "scheduled_at": getattr(
            delivery,
            "scheduled_at",
            None,
        ),
        "picked_up_at": getattr(
            delivery,
            "picked_up_at",
            None,
        ),
        "delivered_at": getattr(
            delivery,
            "delivered_at",
            None,
        ),
        "current_latitude": getattr(
            delivery,
            "current_latitude",
            None,
        ),
        "current_longitude": getattr(
            delivery,
            "current_longitude",
            None,
        ),
        "failure_reason": getattr(
            delivery,
            "failure_reason",
            None,
        ),
    }


def _build_order_response(
    order: Order,
    *,
    customer: User | None = None,
    subscription: Subscription | None = None,
    plan: MealPlan | None = None,
    payment: Payment | None = None,
    delivery: Delivery | None = None,
    driver: User | None = None,
) -> dict[str, Any]:
    meal_statistics = _build_meal_statistics(
        order
    )

    return {
        "id": order.id,
        "order_number": order.order_number,
        "source": _enum_value(order.source),
        "status": _enum_value(order.status),
        "total_amount": order.total_amount,
        "delivery_date": order.delivery_date,
        "delivery_preference_id": (
            order.delivery_preference_id
        ),
        "delivery_place_type": (
            order.delivery_place_type
        ),
        "delivery_place_name": (
            order.delivery_place_name
        ),
        "delivery_city": order.delivery_city,
        "delivery_area": order.delivery_area,
        "delivery_address": (
            order.delivery_address
        ),
        "delivery_latitude": (
            order.delivery_latitude
        ),
        "delivery_longitude": (
            order.delivery_longitude
        ),
        "delivery_notes": order.delivery_notes,
        "items": order.items or [],
        "meal_item_count": meal_statistics[
            "meal_item_count"
        ],
        "total_quantity": meal_statistics[
            "total_quantity"
        ],
        "meal_summary": meal_statistics[
            "meal_summary"
        ],
        "delivery_location_count": (
            meal_statistics[
                "delivery_location_count"
            ]
        ),
        "customer": _build_customer_summary(
            customer
        ),
        "subscription": (
            _build_subscription_summary(
                subscription
            )
        ),
        "plan": _build_plan_summary(plan),
        "payment": _build_payment_summary(
            payment,
            subscription=subscription,
            order=order,
        ),
        "delivery": _build_delivery_summary(
            delivery
        ),
        "driver": _build_driver_summary(driver),
        "timeline": {
            "created_at": order.created_at,
            "confirmed_at": order.confirmed_at,
            "preparation_started_at": (
                order.preparation_started_at
            ),
            "ready_at": order.ready_at,
            "out_for_delivery_at": (
                order.out_for_delivery_at
            ),
            "delivered_at": order.delivered_at,
            "cancelled_at": order.cancelled_at,
            "updated_at": order.updated_at,
        },
        "cancellation": {
            "cancelled_at": order.cancelled_at,
            "reason": order.cancellation_reason,
        },
    }

def _load_related_records(
    db: Session,
    orders: list[Order],
) -> tuple[
    dict[int, User],
    dict[int, Subscription],
    dict[int, MealPlan],
    dict[int, Payment],
    dict[int, Delivery],
    dict[int, User],
]:
    user_ids = {
        order.user_id
        for order in orders
        if order.user_id is not None
    }

    subscription_ids = {
        order.subscription_id
        for order in orders
        if order.subscription_id is not None
    }

    plan_ids = {
        order.plan_id
        for order in orders
        if order.plan_id is not None
    }

    order_ids = {
        order.id
        for order in orders
    }

    customer_map: dict[int, User] = {}
    subscription_map: dict[int, Subscription] = {}
    plan_map: dict[int, MealPlan] = {}
    payment_map: dict[int, Payment] = {}
    delivery_map: dict[int, Delivery] = {}
    driver_map: dict[int, User] = {}

    if user_ids:
        customers = (
            db.query(User)
            .filter(User.id.in_(user_ids))
            .all()
        )

        customer_map = {
            customer.id: customer
            for customer in customers
        }

    if subscription_ids:
        subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.id.in_(
                    subscription_ids
                )
            )
            .all()
        )

        subscription_map = {
            subscription.id: subscription
            for subscription in subscriptions
        }

        payments = (
            db.query(Payment)
            .filter(
                Payment.subscription_id.in_(
                    subscription_ids
                )
            )
            .order_by(Payment.id.desc())
            .all()
        )

        for payment in payments:
            subscription_id = getattr(
                payment,
                "subscription_id",
                None,
            )

            if (
                subscription_id is not None
                and subscription_id
                not in payment_map
            ):
                payment_map[
                    subscription_id
                ] = payment

    if plan_ids:
        plans = (
            db.query(MealPlan)
            .filter(MealPlan.id.in_(plan_ids))
            .all()
        )

        plan_map = {
            plan.id: plan
            for plan in plans
        }

    if order_ids:
        deliveries = (
            db.query(Delivery)
            .filter(
                Delivery.order_id.in_(order_ids)
            )
            .order_by(Delivery.id.desc())
            .all()
        )

        for delivery in deliveries:
            if delivery.order_id not in delivery_map:
                delivery_map[
                    delivery.order_id
                ] = delivery

    driver_ids = {
        delivery.driver_id
        for delivery in delivery_map.values()
        if delivery.driver_id is not None
    }

    if driver_ids:
        drivers = (
            db.query(User)
            .filter(User.id.in_(driver_ids))
            .all()
        )

        driver_map = {
            driver.id: driver
            for driver in drivers
        }

    return (
        customer_map,
        subscription_map,
        plan_map,
        payment_map,
        delivery_map,
        driver_map,
    )


def _serialize_order_list(
    db: Session,
    orders: list[Order],
) -> list[dict[str, Any]]:
    (
        customer_map,
        subscription_map,
        plan_map,
        payment_map,
        delivery_map,
        driver_map,
    ) = _load_related_records(
        db,
        orders,
    )

    results: list[dict[str, Any]] = []

    for order in orders:
        subscription = subscription_map.get(
            order.subscription_id
        )

        plan = plan_map.get(order.plan_id)

        delivery = delivery_map.get(order.id)

        driver = None

        if (
            delivery is not None
            and delivery.driver_id is not None
        ):
            driver = driver_map.get(
                delivery.driver_id
            )

        results.append(
            _build_order_response(
                order,
                customer=customer_map.get(
                    order.user_id
                ),
                subscription=subscription,
                plan=plan,
                payment=payment_map.get(
                    order.subscription_id
                ),
                delivery=delivery,
                driver=driver,
            )
        )

    return results

@router.get("/dashboard")
def orders_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *ORDER_MANAGEMENT_ROLES
        )
    ),
):
    status_rows = (
        db.query(
            Order.status,
            Order.id,
        )
        .all()
    )

    status_counts: dict[str, int] = {}

    for status_value, _order_id in status_rows:
        status_key = str(
            _enum_value(status_value)
        )

        status_counts[status_key] = (
            status_counts.get(status_key, 0)
            + 1
        )

    today = datetime.utcnow().date()

    today_start = datetime.combine(
        today,
        time.min,
    )

    today_end = datetime.combine(
        today,
        time.max,
    )

    orders_today = (
        db.query(Order)
        .filter(
            Order.delivery_date >= today_start,
            Order.delivery_date <= today_end,
        )
        .count()
    )

    ready_for_delivery = (
        db.query(Order)
        .filter(
            Order.status
            == OrderStatus.READY_FOR_DELIVERY
        )
        .count()
    )

    active_orders = (
        db.query(Order)
        .filter(
            Order.status.notin_(
                [
                    OrderStatus.DELIVERED,
                    OrderStatus.CANCELLED,
                ]
            )
        )
        .count()
    )

    automatic_orders = (
        db.query(Order)
        .filter(
            Order.source
            == OrderSource.AUTOMATIC
        )
        .count()
    )

    recent_orders = (
        db.query(Order)
        .order_by(Order.id.desc())
        .limit(10)
        .all()
    )

    return dashboard_response(
        overview={
            "total_orders": len(status_rows),
            "active_orders": active_orders,
            "orders_today": orders_today,
            "ready_for_delivery": (
                ready_for_delivery
            ),
            "automatic_orders": automatic_orders,
        },
        statistics={
            "by_status": status_counts,
        },
        recent_activity=_serialize_order_list(
            db,
            recent_orders,
        ),
    )

@router.get("/my")
def my_orders(
    order_status: OrderStatus | None = Query(
        default=None,
        alias="status",
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    query = (
        db.query(Order)
        .filter(
            Order.user_id == current_user.id
        )
    )

    if order_status is not None:
        query = query.filter(
            Order.status == order_status
        )

    total = query.count()

    orders = (
        query.order_by(Order.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return list_response(
        items=_serialize_order_list(
            db,
            orders,
        ),
        page=page,
        limit=limit,
        total=total,
        message="Your orders were retrieved successfully.",
    )

@router.get("/customer/{customer_id}/history")
def customer_order_history(
    customer_id: int,
    order_status: OrderStatus | None = Query(
        default=None,
        alias="status",
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *ORDER_MANAGEMENT_ROLES
        )
    ),
):
    customer = (
        db.query(User)
        .filter(
            User.id == customer_id,
            User.role == UserRole.CUSTOMER,
        )
        .first()
    )

    if customer is None:
        raise CustomerNotFoundException()

    query = (
        db.query(Order)
        .filter(
            Order.user_id == customer_id
        )
    )

    if order_status is not None:
        query = query.filter(
            Order.status == order_status
        )

    total = query.count()

    orders = (
        query.order_by(Order.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return list_response(
        items=_serialize_order_list(
            db,
            orders,
        ),
        page=page,
        limit=limit,
        total=total,
        message=(
            "Customer order history retrieved "
            "successfully."
        ),
    )

@router.get("/")
def list_orders(
    search: str | None = Query(
        default=None,
        min_length=1,
    ),
    order_status: OrderStatus | None = Query(
        default=None,
        alias="status",
    ),
    source: OrderSource | None = Query(
        default=None,
    ),
    user_id: int | None = Query(
        default=None,
        ge=1,
    ),
    subscription_id: int | None = Query(
        default=None,
        ge=1,
    ),
    plan_id: int | None = Query(
        default=None,
        ge=1,
    ),
    delivery_date: date | None = Query(
        default=None,
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *ORDER_MANAGEMENT_ROLES
        )
    ),
):
    query = db.query(Order)

    if search:
        search_value = f"%{search.strip()}%"

        query = (
            query.outerjoin(
                User,
                User.id == Order.user_id,
            )
            .filter(
                or_(
                    Order.order_number.ilike(
                        search_value
                    ),
                    Order.delivery_address.ilike(
                        search_value
                    ),
                    Order.delivery_place_name.ilike(
                        search_value
                    ),
                    Order.delivery_city.ilike(
                        search_value
                    ),
                    Order.delivery_area.ilike(
                        search_value
                    ),
                    User.first_name.ilike(
                        search_value
                    ),
                    User.last_name.ilike(
                        search_value
                    ),
                    User.email.ilike(
                        search_value
                    ),
                    User.phone.ilike(
                        search_value
                    ),
                )
            )
        )

    if order_status is not None:
        query = query.filter(
            Order.status == order_status
        )

    if source is not None:
        query = query.filter(
            Order.source == source
        )

    if user_id is not None:
        query = query.filter(
            Order.user_id == user_id
        )

    if subscription_id is not None:
        query = query.filter(
            Order.subscription_id
            == subscription_id
        )

    if plan_id is not None:
        query = query.filter(
            Order.plan_id == plan_id
        )

    if delivery_date is not None:
        date_start = datetime.combine(
            delivery_date,
            time.min,
        )

        date_end = datetime.combine(
            delivery_date,
            time.max,
        )

        query = query.filter(
            Order.delivery_date >= date_start,
            Order.delivery_date <= date_end,
        )

    total = query.count()

    orders = (
        query.order_by(Order.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return list_response(
        items=_serialize_order_list(
            db,
            orders,
        ),
        page=page,
        limit=limit,
        total=total,
        message="Orders retrieved successfully.",
    )

@router.get("/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    order = _get_order_or_404(
        db,
        order_id,
    )

    _ensure_order_access(
        order,
        current_user,
    )

    serialized_orders = _serialize_order_list(
        db,
        [order],
    )

    return success_response(
        data=serialized_orders[0],
        message="Order retrieved successfully.",
    )

@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: int,
    reason: str | None = Query(
        default=None,
        max_length=500,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    order = _get_order_or_404(
        db,
        order_id,
    )

    _ensure_order_access(
        order,
        current_user,
    )

    if order.status == OrderStatus.CANCELLED:
        raise BadRequestException(
            "This order is already cancelled."
        )

    blocked_statuses = {
        OrderStatus.PREPARING,
        OrderStatus.READY_FOR_DELIVERY,
        OrderStatus.OUT_FOR_DELIVERY,
        OrderStatus.DELIVERED,
    }

    if order.status in blocked_statuses:
        raise BadRequestException(
            "This order cannot be cancelled after "
            "preparation or delivery processing has started."
        )

    related_delivery = (
        db.query(Delivery)
        .filter(Delivery.order_id == order.id)
        .order_by(Delivery.id.desc())
        .first()
    )

    if related_delivery is not None:
        delivery_status = _enum_value(
            related_delivery.status
        )

        if delivery_status in {
            "picked_up",
            "out_for_delivery",
            "delivered",
        }:
            raise BadRequestException(
                "This order cannot be cancelled because "
                "its delivery is already in progress."
            )

        cancelled_status = getattr(
            type(related_delivery.status),
            "CANCELLED",
            None,
        )

        if cancelled_status is not None:
            related_delivery.status = (
                cancelled_status
            )

    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.utcnow()
    order.cancellation_reason = (
        reason.strip()
        if reason and reason.strip()
        else "Cancelled by user."
    )

    try:
        db.commit()
        db.refresh(order)

    except Exception:
        db.rollback()
        raise

    serialized_orders = _serialize_order_list(
        db,
        [order],
    )

    return updated_response(
        data=serialized_orders[0],
        message="Order cancelled successfully.",
    )