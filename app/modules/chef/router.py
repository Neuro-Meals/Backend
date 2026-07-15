from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.chef.schemas import (
    AssignChefDriverRequest,
    ChefDashboardResponse,
    ChefDeliveryAssignmentResponse,
    ChefDriverResponse,
    ChefOrderResponse,
    ChefStatusResponse,
)
from app.modules.deliveries.models import Delivery, DeliveryStatus
from app.modules.orders.models import Order, OrderStatus
from app.modules.users.models import User, UserRole


router = APIRouter(
    prefix="/chef",
    tags=["Chef"],
)


def enum_value(value):
    if value is None:
        return None

    return value.value if hasattr(value, "value") else value


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

    if order.status != OrderStatus.READY_FOR_DELIVERY:
        raise HTTPException(
            status_code=400,
            detail=(
                "Driver can only be assigned after the order "
                "is ready for delivery"
            ),
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

    existing_delivery = (
        db.query(Delivery)
        .filter(Delivery.order_id == order.id)
        .first()
    )

    if existing_delivery:
        if existing_delivery.status in {
            DeliveryStatus.DELIVERED,
            DeliveryStatus.CANCELLED,
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This order already has a completed or "
                    "cancelled delivery"
                ),
            )

        existing_delivery.driver_id = driver.id
        existing_delivery.status = DeliveryStatus.ASSIGNED

        if payload.scheduled_at is not None:
            existing_delivery.scheduled_at = (
                payload.scheduled_at
            )

        delivery = existing_delivery

    else:
        delivery_address = (
            order.delivery_address
            or getattr(driver, "address", None)
        )

        if not order.delivery_address:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Order does not have a delivery address"
                ),
            )

        delivery = Delivery(
            order_id=order.id,
            user_id=order.user_id,
            driver_id=driver.id,
            status=DeliveryStatus.ASSIGNED,
            delivery_address=order.delivery_address,
            delivery_notes=order.delivery_notes,
            scheduled_at=(
                payload.scheduled_at
                or order.delivery_date
            ),
        )

        db.add(delivery)

    db.commit()
    db.refresh(delivery)
    db.refresh(order)

    return {
        "message": "Driver assigned successfully",
        "delivery_id": delivery.id,
        "order_id": order.id,
        "driver_id": driver.id,
        "delivery_status": delivery.status,
        "order_status": order.status,
    }