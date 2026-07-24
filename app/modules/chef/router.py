from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.chef.schemas import (
    ChefAllergySummaryResponse,
    ChefBulkStatusRequest,
    ChefBulkStatusResponse,
    ChefDashboardResponse,
    ChefMealSummaryResponse,
    ChefOrderResponse,
    ChefStatusResponse,
)
from app.modules.orders.models import Order, OrderStatus
from app.modules.users.models import User, UserRole


router = APIRouter(
    prefix="/chef",
    tags=["Chef"],
)


CHEF_ROLES = (
    UserRole.CHEF,
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
)


KITCHEN_ACTIVE_STATUSES = (
    OrderStatus.SCHEDULED,
    OrderStatus.PENDING,
    OrderStatus.CONFIRMED,
    OrderStatus.PREPARING,
    OrderStatus.READY_FOR_DELIVERY,
)


def enum_value(value):
    if value is None:
        return None
    return value.value if hasattr(value, "value") else value


def normalize_order_items(items: Any) -> list[dict]:
    if items is None:
        return []

    if isinstance(items, list):
        return [
            item
            for item in items
            if isinstance(item, dict)
        ]

    if isinstance(items, dict):
        nested = items.get("items")
        if isinstance(nested, list):
            return [
                item
                for item in nested
                if isinstance(item, dict)
            ]
        return [items]

    return []


def normalize_allergies(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, list):
        values = value
    else:
        return []

    result = []

    for item in values:
        clean = str(item).strip().lower()
        if clean and clean not in result:
            result.append(clean)

    return result


def order_query(db: Session):
    return (
        db.query(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.driver),
            selectinload(Order.meal_category),
        )
    )


def get_order_or_404(
    db: Session,
    order_id: int,
) -> Order:
    order = (
        order_query(db)
        .filter(Order.id == order_id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return order


def customer_payload(user: User | None) -> dict | None:
    if user is None:
        return None

    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": (
            f"{user.first_name or ''} "
            f"{user.last_name or ''}"
        ).strip(),
        "email": user.email,
        "phone": user.phone,
        "allergies": normalize_allergies(
            getattr(user, "allergies", None)
        ),
        "dietary_preference": getattr(
            user,
            "dietary_preference",
            None,
        ),
    }


def driver_payload(user: User | None) -> dict | None:
    if user is None:
        return None

    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": (
            f"{user.first_name or ''} "
            f"{user.last_name or ''}"
        ).strip(),
        "email": user.email,
        "phone": user.phone,
    }


def category_payload(category) -> dict | None:
    if category is None:
        return None

    return {
        "id": category.id,
        "name_en": getattr(category, "name_en", None),
        "name_ar": getattr(category, "name_ar", None),
    }


def build_order_payload(order: Order) -> dict:
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": enum_value(order.status),
        "user_id": order.user_id,
        "subscription_id": order.subscription_id,
        "plan_id": order.plan_id,
        "meal_assignment_id": order.meal_assignment_id,
        "meal_category_id": order.meal_category_id,
        "driver_id": order.driver_id,
        "delivery_preference_id": (
            order.delivery_preference_id
        ),
        "delivery_date": order.delivery_date,
        "delivery_time": order.delivery_time,
        "total_amount": order.total_amount,
        "delivery_place_type": (
            order.delivery_place_type
        ),
        "delivery_place_name": (
            order.delivery_place_name
        ),
        "delivery_city": order.delivery_city,
        "delivery_area": order.delivery_area,
        "delivery_address": order.delivery_address,
        "delivery_latitude": (
            order.delivery_latitude
        ),
        "delivery_longitude": (
            order.delivery_longitude
        ),
        "delivery_notes": order.delivery_notes,
        "items": normalize_order_items(order.items),
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
        "cancellation_reason": (
            order.cancellation_reason
        ),
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "customer": customer_payload(order.customer),
        "driver": driver_payload(order.driver),
        "meal_category": category_payload(
            order.meal_category
        ),
    }


def orders_for_date_query(
    db: Session,
    target_date: date,
):
    return (
        order_query(db)
        .filter(Order.delivery_date == target_date)
    )


def status_count(
    db: Session,
    target_date: date,
    status: OrderStatus,
) -> int:
    return (
        db.query(Order)
        .filter(
            Order.delivery_date == target_date,
            Order.status == status,
        )
        .count()
    )


@router.get(
    "/dashboard",
    response_model=ChefDashboardResponse,
)
def chef_dashboard(
    target_date: date = Query(
        default_factory=date.today,
        alias="date",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    orders = (
        orders_for_date_query(db, target_date)
        .all()
    )

    items = [
        item
        for order in orders
        for item in normalize_order_items(order.items)
    ]

    return {
        "date": target_date,
        "total_orders": len(orders),
        "scheduled_orders": status_count(
            db, target_date, OrderStatus.SCHEDULED
        ),
        "pending_orders": status_count(
            db, target_date, OrderStatus.PENDING
        ),
        "confirmed_orders": status_count(
            db, target_date, OrderStatus.CONFIRMED
        ),
        "preparing_orders": status_count(
            db, target_date, OrderStatus.PREPARING
        ),
        "ready_for_delivery_orders": status_count(
            db,
            target_date,
            OrderStatus.READY_FOR_DELIVERY,
        ),
        "out_for_delivery_orders": status_count(
            db,
            target_date,
            OrderStatus.OUT_FOR_DELIVERY,
        ),
        "delivered_orders": status_count(
            db, target_date, OrderStatus.DELIVERED
        ),
        "cancelled_orders": status_count(
            db, target_date, OrderStatus.CANCELLED
        ),
        "total_meal_items": len(items),
        "total_meal_quantity": sum(
            max(int(item.get("quantity") or 1), 1)
            for item in items
        ),
    }


@router.get("/orders")
def chef_orders(
    status: OrderStatus | None = Query(None),
    search: str | None = Query(None),
    delivery_date: date | None = Query(None),
    meal_category_id: int | None = Query(
        None,
        ge=1,
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    query = order_query(db)

    if status is not None:
        query = query.filter(Order.status == status)
    else:
        query = query.filter(
            Order.status.in_(KITCHEN_ACTIVE_STATUSES)
        )

    if delivery_date is not None:
        query = query.filter(
            Order.delivery_date == delivery_date
        )

    if meal_category_id is not None:
        query = query.filter(
            Order.meal_category_id == meal_category_id
        )

    if search:
        value = f"%{search.strip()}%"

        query = (
            query.join(
                User,
                User.id == Order.user_id,
            )
            .filter(
                or_(
                    Order.order_number.ilike(value),
                    Order.delivery_address.ilike(value),
                    User.first_name.ilike(value),
                    User.last_name.ilike(value),
                    User.email.ilike(value),
                    User.phone.ilike(value),
                )
            )
        )

    total = query.count()

    orders = (
        query.order_by(
            Order.delivery_date.asc(),
            Order.delivery_time.asc(),
            Order.meal_category_id.asc(),
            Order.id.asc(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": [
            build_order_payload(order)
            for order in orders
        ],
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


@router.get("/orders/today")
def chef_today_orders(
    include_completed: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    target_date = date.today()

    query = orders_for_date_query(
        db,
        target_date,
    )

    if not include_completed:
        query = query.filter(
            Order.status.in_(KITCHEN_ACTIVE_STATUSES)
        )

    orders = (
        query.order_by(
            Order.delivery_time.asc(),
            Order.meal_category_id.asc(),
            Order.id.asc(),
        )
        .all()
    )

    return {
        "date": target_date,
        "total": len(orders),
        "data": [
            build_order_payload(order)
            for order in orders
        ],
    }


@router.get("/orders/tomorrow")
def chef_tomorrow_orders(
    include_completed: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    target_date = date.today() + timedelta(days=1)

    query = orders_for_date_query(
        db,
        target_date,
    )

    if not include_completed:
        query = query.filter(
            Order.status.in_(KITCHEN_ACTIVE_STATUSES)
        )

    orders = (
        query.order_by(
            Order.delivery_time.asc(),
            Order.meal_category_id.asc(),
            Order.id.asc(),
        )
        .all()
    )

    return {
        "date": target_date,
        "total": len(orders),
        "data": [
            build_order_payload(order)
            for order in orders
        ],
    }


@router.get("/orders/grouped")
def chef_orders_grouped(
    target_date: date = Query(
        default_factory=date.today,
        alias="date",
    ),
    include_completed: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    query = orders_for_date_query(
        db,
        target_date,
    )

    if not include_completed:
        query = query.filter(
            Order.status.in_(KITCHEN_ACTIVE_STATUSES)
        )

    orders = (
        query.order_by(
            Order.delivery_time.asc(),
            Order.meal_category_id.asc(),
            Order.id.asc(),
        )
        .all()
    )

    grouped: dict[int, dict] = {}

    for order in orders:
        category_id = order.meal_category_id
        category = order.meal_category

        if category_id not in grouped:
            grouped[category_id] = {
                "meal_category_id": category_id,
                "category_name": getattr(
                    category,
                    "name_en",
                    None,
                ),
                "category_name_ar": getattr(
                    category,
                    "name_ar",
                    None,
                ),
                "order_count": 0,
                "total_quantity": 0,
                "orders": [],
            }

        payload = build_order_payload(order)
        quantity = sum(
            max(int(item.get("quantity") or 1), 1)
            for item in normalize_order_items(
                order.items
            )
        )

        grouped[category_id]["order_count"] += 1
        grouped[category_id][
            "total_quantity"
        ] += quantity
        grouped[category_id]["orders"].append(
            payload
        )

    groups = list(grouped.values())
    groups.sort(
        key=lambda item: (
            item["category_name"] or ""
        ).lower()
    )

    return {
        "date": target_date,
        "total_orders": len(orders),
        "groups": groups,
    }


@router.get(
    "/orders/{order_id}",
    response_model=ChefOrderResponse,
)
def chef_get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    return build_order_payload(
        get_order_or_404(db, order_id)
    )


@router.patch(
    "/orders/{order_id}/start-preparing",
    response_model=ChefStatusResponse,
)
def chef_start_preparing(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    order = get_order_or_404(db, order_id)

    if order.status not in {
        OrderStatus.PENDING,
        OrderStatus.CONFIRMED,
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Only pending or confirmed orders can "
                "start preparation"
            ),
        )

    order.status = OrderStatus.PREPARING
    order.preparation_started_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Order preparation started",
        "order": build_order_payload(order),
    }


@router.patch(
    "/orders/{order_id}/ready",
    response_model=ChefStatusResponse,
)
def chef_mark_ready(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    order = get_order_or_404(db, order_id)

    if order.status != OrderStatus.PREPARING:
        raise HTTPException(
            status_code=409,
            detail=(
                "Only preparing orders can be marked "
                "ready for delivery"
            ),
        )

    order.status = OrderStatus.READY_FOR_DELIVERY
    order.ready_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Order is ready for delivery",
        "order": build_order_payload(order),
    }


def bulk_change_status(
    db: Session,
    order_ids: list[int],
    *,
    expected_statuses: set[OrderStatus],
    new_status: OrderStatus,
) -> dict:
    unique_ids = list(dict.fromkeys(order_ids))
    updated = []
    failures = []
    now = datetime.utcnow()

    for order_id in unique_ids:
        order = (
            db.query(Order)
            .filter(Order.id == order_id)
            .first()
        )

        if order is None:
            failures.append(
                {
                    "order_id": order_id,
                    "reason": "Order not found",
                }
            )
            continue

        if order.status not in expected_statuses:
            failures.append(
                {
                    "order_id": order.id,
                    "reason": (
                        f"Order status is "
                        f"{enum_value(order.status)}"
                    ),
                }
            )
            continue

        order.status = new_status

        if new_status == OrderStatus.PREPARING:
            order.preparation_started_at = now

        if (
            new_status
            == OrderStatus.READY_FOR_DELIVERY
        ):
            order.ready_at = now

        updated.append(
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "status": new_status,
            }
        )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Bulk status update completed",
        "requested_orders": len(unique_ids),
        "updated_orders": len(updated),
        "failed_orders": len(failures),
        "orders": updated,
        "failures": failures,
    }


@router.patch(
    "/orders/bulk/start-preparing",
    response_model=ChefBulkStatusResponse,
)
def chef_bulk_start_preparing(
    payload: ChefBulkStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    return bulk_change_status(
        db=db,
        order_ids=payload.order_ids,
        expected_statuses={
            OrderStatus.PENDING,
            OrderStatus.CONFIRMED,
        },
        new_status=OrderStatus.PREPARING,
    )


@router.patch(
    "/orders/bulk/ready",
    response_model=ChefBulkStatusResponse,
)
def chef_bulk_mark_ready(
    payload: ChefBulkStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    return bulk_change_status(
        db=db,
        order_ids=payload.order_ids,
        expected_statuses={
            OrderStatus.PREPARING,
        },
        new_status=OrderStatus.READY_FOR_DELIVERY,
    )


@router.get(
    "/meals/summary",
    response_model=ChefMealSummaryResponse,
)
def chef_meal_summary(
    target_date: date = Query(
        default_factory=date.today,
        alias="date",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    orders = (
        orders_for_date_query(db, target_date)
        .filter(
            Order.status.in_(KITCHEN_ACTIVE_STATUSES)
        )
        .all()
    )

    summary: dict[str, dict] = {}

    for order in orders:
        for item in normalize_order_items(
            order.items
        ):
            meal_id = item.get("meal_id")
            meal_name = str(
                item.get("meal_name")
                or item.get("name_en")
                or "Unknown meal"
            ).strip()

            try:
                quantity = max(
                    int(item.get("quantity") or 1),
                    1,
                )
            except (TypeError, ValueError):
                quantity = 1

            key = (
                f"id:{meal_id}"
                if meal_id is not None
                else f"name:{meal_name.lower()}"
            )

            if key not in summary:
                summary[key] = {
                    "meal_id": meal_id,
                    "meal_name": meal_name,
                    "quantity": 0,
                }

            summary[key]["quantity"] += quantity

    meals = sorted(
        summary.values(),
        key=lambda item: (
            -item["quantity"],
            item["meal_name"].lower(),
        ),
    )

    return {
        "date": target_date,
        "total_orders": len(orders),
        "total_meals": sum(
            item["quantity"]
            for item in meals
        ),
        "meals": meals,
    }


@router.get(
    "/allergies/summary",
    response_model=ChefAllergySummaryResponse,
)
def chef_allergy_summary(
    target_date: date = Query(
        default_factory=date.today,
        alias="date",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*CHEF_ROLES)
    ),
):
    orders = (
        orders_for_date_query(db, target_date)
        .filter(
            Order.status.in_(KITCHEN_ACTIVE_STATUSES)
        )
        .all()
    )

    user_order_ids: dict[int, list[int]] = (
        defaultdict(list)
    )

    for order in orders:
        user_order_ids[order.user_id].append(
            order.id
        )

    users = []

    if user_order_ids:
        users = (
            db.query(User)
            .filter(
                User.id.in_(
                    list(user_order_ids.keys())
                )
            )
            .all()
        )

    allergy_users: dict[str, set[int]] = (
        defaultdict(set)
    )
    allergy_orders: dict[str, set[int]] = (
        defaultdict(set)
    )
    customers = []

    for user in users:
        allergies = normalize_allergies(
            getattr(user, "allergies", None)
        )

        if not allergies:
            continue

        order_ids = user_order_ids.get(
            user.id,
            [],
        )

        for allergy in allergies:
            allergy_users[allergy].add(user.id)
            allergy_orders[allergy].update(
                order_ids
            )

        customers.append(
            {
                "user_id": user.id,
                "full_name": (
                    f"{user.first_name or ''} "
                    f"{user.last_name or ''}"
                ).strip(),
                "phone": user.phone,
                "allergies": allergies,
                "order_ids": order_ids,
            }
        )

    allergy_results = [
        {
            "allergy": allergy,
            "customer_count": len(
                allergy_users[allergy]
            ),
            "order_count": len(
                allergy_orders[allergy]
            ),
        }
        for allergy in sorted(
            allergy_users.keys()
        )
    ]

    customers.sort(
        key=lambda item: item[
            "full_name"
        ].lower()
    )

    return {
        "date": target_date,
        "total_orders": len(orders),
        "customers_with_allergies": len(
            customers
        ),
        "allergies": allergy_results,
        "customers": customers,
    }