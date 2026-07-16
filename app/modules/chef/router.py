from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.chef.schemas import (
    AssignChefDriverRequest,
    BulkAssignChefDriverRequest,
    BulkChefDriverAssignmentResponse,
    ChefAllergySummaryResponse,
    ChefDashboardResponse,
    ChefDeliveryAssignmentResponse,
    ChefDriverResponse,
    ChefMealSummaryResponse,
    ChefOrderResponse,
    ChefStatusResponse,
)
from app.modules.deliveries.models import Delivery, DeliveryStatus
from app.modules.orders.models import Order, OrderStatus
from app.modules.users.models import User, UserRole
from collections import defaultdict
from typing import Any
from sqlalchemy.exc import IntegrityError


router = APIRouter(
    prefix="/chef",
    tags=["Chef"],
)


def enum_value(value):
    if value is None:
        return None

    return value.value if hasattr(value, "value") else value

KITCHEN_ORDER_STATUSES = [
    OrderStatus.PENDING,
    OrderStatus.CONFIRMED,
    OrderStatus.PREPARING,
    OrderStatus.READY_FOR_DELIVERY,
]

def assign_order_to_driver(
    db: Session,
    order: Order,
    driver: User,
    scheduled_at: datetime | None = None,
) -> Delivery:
    if order.status != OrderStatus.READY_FOR_DELIVERY:
        raise ValueError(
            "Order is not ready for delivery"
        )

    if not order.delivery_address:
        raise ValueError(
            "Order does not have a delivery address"
        )

    delivery = (
        db.query(Delivery)
        .filter(Delivery.order_id == order.id)
        .first()
    )

    if delivery is not None:
        if delivery.status == DeliveryStatus.DELIVERED:
            raise ValueError(
                "Order delivery is already completed"
            )

        if delivery.status == DeliveryStatus.CANCELLED:
            raise ValueError(
                "Order delivery is cancelled"
            )

        delivery.driver_id = driver.id
        delivery.status = DeliveryStatus.ASSIGNED

        if scheduled_at is not None:
            delivery.scheduled_at = scheduled_at

        if not delivery.delivery_address:
            delivery.delivery_address = (
                order.delivery_address
            )

        if not delivery.delivery_notes:
            delivery.delivery_notes = (
                order.delivery_notes
            )

    else:
        delivery = Delivery(
            order_id=order.id,
            user_id=order.user_id,
            driver_id=driver.id,
            status=DeliveryStatus.ASSIGNED,
            delivery_address=order.delivery_address,
            delivery_notes=order.delivery_notes,
            scheduled_at=(
                scheduled_at
                or order.delivery_date
            ),
        )

        db.add(delivery)

    return delivery


def get_date_range(target_date: date) -> tuple[datetime, datetime]:
    start_datetime = datetime.combine(
        target_date,
        time.min,
    )

    end_datetime = start_datetime + timedelta(days=1)

    return start_datetime, end_datetime


def get_orders_for_delivery_date(
    db: Session,
    target_date: date,
    include_completed: bool = False,
) -> list[Order]:
    start_datetime, end_datetime = get_date_range(
        target_date
    )

    query = db.query(Order).filter(
        Order.delivery_date >= start_datetime,
        Order.delivery_date < end_datetime,
    )

    if not include_completed:
        query = query.filter(
            Order.status.in_(KITCHEN_ORDER_STATUSES)
        )

    return (
        query.order_by(
            Order.delivery_date.asc(),
            Order.id.asc(),
        )
        .all()
    )


def normalize_order_items(
    items: Any,
) -> list[dict]:
    """
    Convert Order.items into a predictable list of dictionaries.

    Supported examples:

    [
        {
            "meal_id": 1,
            "meal_name": "Chicken Bowl",
            "quantity": 2
        }
    ]

    or:

    {
        "items": [...]
    }
    """

    if items is None:
        return []

    if isinstance(items, dict):
        nested_items = items.get("items")

        if isinstance(nested_items, list):
            return [
                item
                for item in nested_items
                if isinstance(item, dict)
            ]

        return [items]

    if isinstance(items, list):
        return [
            item
            for item in items
            if isinstance(item, dict)
        ]

    return []


def extract_meal_id(item: dict) -> int | None:
    raw_value = (
        item.get("meal_id")
        or item.get("id")
    )

    if raw_value is None:
        return None

    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def extract_meal_name(item: dict) -> str:
    return str(
        item.get("meal_name")
        or item.get("name_en")
        or item.get("name")
        or item.get("title")
        or item.get("plan_name")
        or "Unknown meal"
    ).strip()


def extract_item_quantity(item: dict) -> int:
    raw_value = (
        item.get("quantity")
        or item.get("qty")
        or item.get("count")
        or 1
    )

    try:
        quantity = int(raw_value)
    except (TypeError, ValueError):
        quantity = 1

    return max(quantity, 1)


def normalize_allergies(
    allergies: Any,
) -> list[str]:
    if allergies is None:
        return []

    if isinstance(allergies, list):
        values = allergies

    elif isinstance(allergies, str):
        values = allergies.split(",")

    else:
        return []

    normalized = []

    for allergy in values:
        clean_allergy = str(allergy).strip().lower()

        if clean_allergy and clean_allergy not in normalized:
            normalized.append(clean_allergy)

    return normalized


def build_customer_payload(
    customer: User | None,
) -> dict | None:
    if customer is None:
        return None

    return {
        "id": customer.id,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "full_name": (
            f"{customer.first_name} {customer.last_name}"
        ),
        "email": customer.email,
        "phone": customer.phone,
        "location": getattr(customer, "location", None),
        "address": getattr(customer, "address", None),
    }


def build_delivery_payload(
    delivery: Delivery | None,
) -> dict | None:
    if delivery is None:
        return None

    return {
        "id": delivery.id,
        "driver_id": delivery.driver_id,
        "status": enum_value(delivery.status),
        "delivery_address": delivery.delivery_address,
        "scheduled_at": delivery.scheduled_at,
        "picked_up_at": delivery.picked_up_at,
        "delivered_at": delivery.delivered_at,
    }


def build_order_payload(
    db: Session,
    order: Order,
) -> dict:
    customer = (
        db.query(User)
        .filter(User.id == order.user_id)
        .first()
    )

    delivery = (
        db.query(Delivery)
        .filter(Delivery.order_id == order.id)
        .first()
    )

    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": enum_value(order.status),
        "user_id": order.user_id,
        "subscription_id": order.subscription_id,
        "plan_id": order.plan_id,
        "total_amount": order.total_amount,
        "delivery_date": order.delivery_date,
        "delivery_address": order.delivery_address,
        "delivery_notes": order.delivery_notes,
        "items": order.items,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "customer": build_customer_payload(customer),
        "delivery": build_delivery_payload(delivery),
    }


def get_order_or_404(
    db: Session,
    order_id: int,
) -> Order:
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return order


@router.get(
    "/dashboard",
    response_model=ChefDashboardResponse,
)
def chef_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    total_orders = db.query(Order).count()

    pending_orders = (
        db.query(Order)
        .filter(Order.status == OrderStatus.PENDING)
        .count()
    )

    confirmed_orders = (
        db.query(Order)
        .filter(Order.status == OrderStatus.CONFIRMED)
        .count()
    )

    preparing_orders = (
        db.query(Order)
        .filter(Order.status == OrderStatus.PREPARING)
        .count()
    )

    ready_orders = (
        db.query(Order)
        .filter(
            Order.status == OrderStatus.READY_FOR_DELIVERY
        )
        .count()
    )

    out_for_delivery_orders = (
        db.query(Order)
        .filter(
            Order.status == OrderStatus.OUT_FOR_DELIVERY
        )
        .count()
    )

    delivered_orders = (
        db.query(Order)
        .filter(Order.status == OrderStatus.DELIVERED)
        .count()
    )

    cancelled_orders = (
        db.query(Order)
        .filter(Order.status == OrderStatus.CANCELLED)
        .count()
    )

    deliveries_needed = (
        db.query(Order)
        .outerjoin(
            Delivery,
            Delivery.order_id == Order.id,
        )
        .filter(
            Order.status == OrderStatus.READY_FOR_DELIVERY,
            Delivery.id.is_(None),
        )
        .count()
    )

    assigned_deliveries = (
        db.query(Delivery)
        .filter(
            Delivery.status.in_(
                [
                    DeliveryStatus.ASSIGNED,
                    DeliveryStatus.PICKED_UP,
                    DeliveryStatus.OUT_FOR_DELIVERY,
                ]
            )
        )
        .count()
    )

    active_drivers = (
        db.query(User)
        .filter(
            User.role == UserRole.DRIVER,
            User.is_active.is_(True),
        )
        .all()
    )

    busy_driver_ids = {
        driver_id
        for (driver_id,) in (
            db.query(Delivery.driver_id)
            .filter(
                Delivery.driver_id.isnot(None),
                Delivery.status.in_(
                    [
                        DeliveryStatus.ASSIGNED,
                        DeliveryStatus.PICKED_UP,
                        DeliveryStatus.OUT_FOR_DELIVERY,
                    ]
                ),
            )
            .distinct()
            .all()
        )
    }

    available_drivers = sum(
        1
        for driver in active_drivers
        if driver.id not in busy_driver_ids
    )

    return ChefDashboardResponse(
        total_orders=total_orders,
        pending_orders=pending_orders,
        confirmed_orders=confirmed_orders,
        preparing_orders=preparing_orders,
        ready_for_delivery_orders=ready_orders,
        out_for_delivery_orders=out_for_delivery_orders,
        delivered_orders=delivered_orders,
        cancelled_orders=cancelled_orders,
        deliveries_needed=deliveries_needed,
        assigned_deliveries=assigned_deliveries,
        available_drivers=available_drivers,
        total_active_drivers=len(active_drivers),
    )


@router.get(
    "/orders",
)
def chef_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
    status: OrderStatus | None = Query(None),
    search: str | None = Query(None),
    delivery_date: date | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Order)

    if status is not None:
        query = query.filter(Order.status == status)
    else:
        # By default, show the kitchen-relevant queue.
        query = query.filter(
            Order.status.in_(
                [
                    OrderStatus.PENDING,
                    OrderStatus.CONFIRMED,
                    OrderStatus.PREPARING,
                    OrderStatus.READY_FOR_DELIVERY,
                ]
            )
        )

    if search:
        search_value = f"%{search.strip()}%"

        query = (
            query.join(
                User,
                User.id == Order.user_id,
            )
            .filter(
                or_(
                    Order.order_number.ilike(search_value),
                    Order.delivery_address.ilike(search_value),
                    User.first_name.ilike(search_value),
                    User.last_name.ilike(search_value),
                    User.email.ilike(search_value),
                    User.phone.ilike(search_value),
                )
            )
        )

    if delivery_date is not None:
        start_datetime = datetime.combine(
            delivery_date,
            time.min,
        )
        end_datetime = start_datetime + timedelta(days=1)

        query = query.filter(
            Order.delivery_date >= start_datetime,
            Order.delivery_date < end_datetime,
        )

    total = query.count()

    orders = (
        query.order_by(
            Order.delivery_date.asc().nullslast(),
            Order.id.asc(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": [
            build_order_payload(db, order)
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
    
    
@router.get(
    "/orders/today",
)
def chef_today_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
    include_completed: bool = Query(False),
):
    target_date = date.today()

    orders = get_orders_for_delivery_date(
        db=db,
        target_date=target_date,
        include_completed=include_completed,
    )

    return {
        "date": target_date,
        "total": len(orders),
        "data": [
            build_order_payload(db, order)
            for order in orders
        ],
    }    

@router.get(
    "/orders/tomorrow",
)
def chef_tomorrow_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
    include_completed: bool = Query(False),
):
    target_date = date.today() + timedelta(days=1)

    orders = get_orders_for_delivery_date(
        db=db,
        target_date=target_date,
        include_completed=include_completed,
    )

    return {
        "date": target_date,
        "total": len(orders),
        "data": [
            build_order_payload(db, order)
            for order in orders
        ],
    }
    
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
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    orders = get_orders_for_delivery_date(
        db=db,
        target_date=target_date,
        include_completed=False,
    )

    meal_summary: dict[str, dict] = {}

    for order in orders:
        order_items = normalize_order_items(
            order.items
        )

        for item in order_items:
            meal_id = extract_meal_id(item)
            meal_name = extract_meal_name(item)
            quantity = extract_item_quantity(item)

            summary_key = (
                f"id:{meal_id}"
                if meal_id is not None
                else f"name:{meal_name.lower()}"
            )

            if summary_key not in meal_summary:
                meal_summary[summary_key] = {
                    "meal_id": meal_id,
                    "meal_name": meal_name,
                    "quantity": 0,
                }

            meal_summary[summary_key]["quantity"] += quantity

    meals = sorted(
        meal_summary.values(),
        key=lambda item: (
            -item["quantity"],
            item["meal_name"].lower(),
        ),
    )

    total_meals = sum(
        item["quantity"]
        for item in meals
    )

    return {
        "date": target_date,
        "total_orders": len(orders),
        "total_meals": total_meals,
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
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    orders = get_orders_for_delivery_date(
        db=db,
        target_date=target_date,
        include_completed=False,
    )

    user_order_ids: dict[int, list[int]] = defaultdict(list)

    for order in orders:
        user_order_ids[order.user_id].append(
            order.id
        )

    user_ids = list(user_order_ids.keys())

    customers = []

    if user_ids:
        customers = (
            db.query(User)
            .filter(User.id.in_(user_ids))
            .all()
        )

    allergy_customer_ids: dict[str, set[int]] = defaultdict(set)
    allergy_order_ids: dict[str, set[int]] = defaultdict(set)

    customer_results = []

    for customer in customers:
        allergies = normalize_allergies(
            customer.allergies
        )

        if not allergies:
            continue

        order_ids = user_order_ids.get(
            customer.id,
            [],
        )

        for allergy in allergies:
            allergy_customer_ids[allergy].add(
                customer.id
            )

            allergy_order_ids[allergy].update(
                order_ids
            )

        customer_results.append(
            {
                "user_id": customer.id,
                "full_name": (
                    f"{customer.first_name} "
                    f"{customer.last_name}"
                ).strip(),
                "phone": customer.phone,
                "allergies": allergies,
                "order_ids": order_ids,
            }
        )

    allergy_results = []

    for allergy in sorted(
        allergy_customer_ids.keys()
    ):
        allergy_results.append(
            {
                "allergy": allergy,
                "customer_count": len(
                    allergy_customer_ids[allergy]
                ),
                "order_count": len(
                    allergy_order_ids[allergy]
                ),
            }
        )

    customer_results.sort(
        key=lambda customer: customer["full_name"].lower()
    )

    return {
        "date": target_date,
        "total_orders": len(orders),
        "customers_with_allergies": len(
            customer_results
        ),
        "allergies": allergy_results,
        "customers": customer_results,
    }        

@router.get(
    "/orders/ready-for-delivery",
)
def chef_ready_for_delivery_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
    unassigned_only: bool = Query(False),
    target_date: date | None = Query(
        None,
        alias="date",
    ),
):
    query = (
        db.query(Order)
        .outerjoin(
            Delivery,
            Delivery.order_id == Order.id,
        )
        .filter(
            Order.status
            == OrderStatus.READY_FOR_DELIVERY
        )
    )

    if unassigned_only:
        query = query.filter(
            or_(
                Delivery.id.is_(None),
                Delivery.driver_id.is_(None),
            )
        )

    if target_date is not None:
        start_datetime, end_datetime = get_date_range(
            target_date
        )

        query = query.filter(
            Order.delivery_date >= start_datetime,
            Order.delivery_date < end_datetime,
        )

    orders = (
        query.order_by(
            Order.delivery_date.asc().nullslast(),
            Order.id.asc(),
        )
        .all()
    )

    return {
        "date": target_date,
        "unassigned_only": unassigned_only,
        "total": len(orders),
        "data": [
            build_order_payload(db, order)
            for order in orders
        ],
    }
    
@router.post(
    "/orders/bulk-assign-driver",
    response_model=BulkChefDriverAssignmentResponse,
)
def chef_bulk_assign_driver(
    payload: BulkAssignChefDriverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    driver = (
        db.query(User)
        .filter(
            User.id == payload.driver_id,
            User.role == UserRole.DRIVER,
            User.is_active.is_(True),
        )
        .first()
    )

    if driver is None:
        raise HTTPException(
            status_code=404,
            detail="Driver not found or inactive",
        )

    unique_order_ids = list(
        dict.fromkeys(payload.order_ids)
    )

    assignments = []
    failures = []

    for order_id in unique_order_ids:
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

        if (
            order.status
            != OrderStatus.READY_FOR_DELIVERY
        ):
            failures.append(
                {
                    "order_id": order.id,
                    "reason": (
                        "Order must be ready_for_delivery "
                        "before assigning a driver"
                    ),
                }
            )
            continue

        if not order.delivery_address:
            failures.append(
                {
                    "order_id": order.id,
                    "reason": (
                        "Order delivery address is missing"
                    ),
                }
            )
            continue

        try:
            delivery = assign_order_to_driver(
                db=db,
                order=order,
                driver=driver,
                scheduled_at=payload.scheduled_at,
            )

            # Flush so a newly created delivery receives its ID.
            db.flush()

            assignments.append(
                {
                    "order_id": order.id,
                    "delivery_id": delivery.id,
                    "driver_id": driver.id,
                    "order_status": enum_value(
                        order.status
                    ),
                    "delivery_status": enum_value(
                        delivery.status
                    ),
                }
            )

        except ValueError as exc:
            failures.append(
                {
                    "order_id": order.id,
                    "reason": str(exc),
                }
            )

        except IntegrityError:
            db.rollback()

            raise HTTPException(
                status_code=409,
                detail=(
                    "A database conflict occurred while "
                    "assigning the selected orders"
                ),
            )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "Bulk driver assignment could not "
                "be completed"
            ),
        ) from exc

    return {
        "message": (
            "Bulk driver assignment completed"
        ),
        "driver_id": driver.id,
        "requested_orders": len(
            unique_order_ids
        ),
        "assigned_orders": len(assignments),
        "failed_orders": len(failures),
        "assignments": assignments,
        "failures": failures,
    }    

@router.get(
    "/orders/{order_id}",
    response_model=ChefOrderResponse,
)
def chef_get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    order = get_order_or_404(
        db=db,
        order_id=order_id,
    )

    return build_order_payload(
        db=db,
        order=order,
    )


@router.patch(
    "/orders/{order_id}/start-preparing",
    response_model=ChefStatusResponse,
)
def chef_start_preparing(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    order = get_order_or_404(
        db=db,
        order_id=order_id,
    )

    allowed_statuses = {
        OrderStatus.PENDING,
        OrderStatus.CONFIRMED,
    }

    if order.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only pending or confirmed orders can "
                "start preparation"
            ),
        )

    order.status = OrderStatus.PREPARING

    db.commit()
    db.refresh(order)

    return {
        "message": "Order preparation started",
        "order": build_order_payload(db, order),
    }


@router.patch(
    "/orders/{order_id}/ready",
    response_model=ChefStatusResponse,
)
def chef_mark_ready(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    order = get_order_or_404(
        db=db,
        order_id=order_id,
    )

    if order.status != OrderStatus.PREPARING:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only an order that is currently preparing "
                "can be marked ready"
            ),
        )

    order.status = OrderStatus.READY_FOR_DELIVERY

    db.commit()
    db.refresh(order)

    return {
        "message": "Order is ready for delivery",
        "order": build_order_payload(db, order),
    }


@router.get(
    "/drivers",
    response_model=list[ChefDriverResponse],
)
def chef_drivers(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
    available_only: bool = Query(False),
):
    drivers = (
        db.query(User)
        .filter(
            User.role == UserRole.DRIVER,
            User.is_active.is_(True),
        )
        .order_by(
            User.first_name.asc(),
            User.last_name.asc(),
        )
        .all()
    )

    results = []

    for driver in drivers:
        active_deliveries = (
            db.query(Delivery)
            .filter(
                Delivery.driver_id == driver.id,
                Delivery.status.in_(
                    [
                        DeliveryStatus.ASSIGNED,
                        DeliveryStatus.PICKED_UP,
                        DeliveryStatus.OUT_FOR_DELIVERY,
                    ]
                ),
            )
            .count()
        )

        available = active_deliveries == 0

        if available_only and not available:
            continue

        results.append(
            {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "full_name": (
                    f"{driver.first_name} {driver.last_name}"
                ),
                "email": driver.email,
                "phone": driver.phone,
                "location": getattr(
                    driver,
                    "location",
                    None,
                ),
                "is_active": driver.is_active,
                "active_deliveries": active_deliveries,
                "available": available,
            }
        )

    return results


@router.post(
    "/orders/{order_id}/assign-driver",
    response_model=ChefDeliveryAssignmentResponse,
)
def chef_assign_driver(
    order_id: int,
    payload: AssignChefDriverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.CHEF,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    order = get_order_or_404(
        db=db,
        order_id=order_id,
    )

    driver = (
        db.query(User)
        .filter(
            User.id == payload.driver_id,
            User.role == UserRole.DRIVER,
            User.is_active.is_(True),
        )
        .first()
    )

    if driver is None:
        raise HTTPException(
            status_code=404,
            detail="Driver not found or inactive",
        )

    try:
        delivery = assign_order_to_driver(
            db=db,
            order=order,
            driver=driver,
            scheduled_at=payload.scheduled_at,
        )

        db.commit()
        db.refresh(delivery)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "Driver assignment could not "
                "be completed"
            ),
        ) from exc

    return {
        "message": "Driver assigned successfully",
        "delivery_id": delivery.id,
        "order_id": order.id,
        "driver_id": driver.id,
        "delivery_status": delivery.status,
        "order_status": order.status,
    }