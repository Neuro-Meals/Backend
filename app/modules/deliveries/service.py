from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.modules.customer_drivers.models import CustomerDriverAssignment
from app.modules.deliveries.models import Delivery, DeliveryStatus
from app.modules.orders.models import Order, OrderStatus
from app.modules.users.models import User, UserRole
from sqlalchemy.exc import IntegrityError

from app.modules.orders.models import Order, OrderStatus


def get_delivery_for_order(
    db: Session,
    order_id: int,
) -> Delivery | None:
    return (
        db.query(Delivery)
        .filter(Delivery.order_id == order_id)
        .first()
    )


def ensure_delivery_for_order(
    db: Session,
    order: Order,
    *,
    commit: bool = False,
) -> Delivery:
    """
    Create the tracking row for an order exactly once.

    The order must already have a driver and delivery location.
    """

    existing = get_delivery_for_order(
        db=db,
        order_id=order.id,
    )

    if existing is not None:
        if (
            order.status
            == OrderStatus.READY_FOR_DELIVERY
            and existing.status == DeliveryStatus.PENDING
        ):
            existing.status = (
                DeliveryStatus.READY_FOR_PICKUP
            )
            existing.ready_for_pickup_at = (
                existing.ready_for_pickup_at
                or datetime.utcnow()
            )

        if commit:
            db.commit()
            db.refresh(existing)

        return existing

    if order.driver_id is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Order has no assigned driver and cannot "
                "create a delivery"
            ),
        )

    if not order.delivery_address:
        raise HTTPException(
            status_code=409,
            detail=(
                "Order has no delivery address and cannot "
                "create a delivery"
            ),
        )

    initial_status = DeliveryStatus.PENDING
    ready_at = None

    if order.status == OrderStatus.READY_FOR_DELIVERY:
        initial_status = (
            DeliveryStatus.READY_FOR_PICKUP
        )
        ready_at = datetime.utcnow()

    delivery = Delivery(
        order_id=order.id,
        status=initial_status,
        ready_for_pickup_at=ready_at,
    )

    db.add(delivery)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()

        existing = get_delivery_for_order(
            db=db,
            order_id=order.id,
        )

        if existing is None:
            raise

        return existing

    if commit:
        db.commit()
        db.refresh(delivery)

    return delivery


def start_of_day(target_date: date | None = None) -> datetime:
    """
    Return the beginning of a date.

    When target_date is not supplied, today's UTC date is used.
    """

    selected_date = target_date or datetime.utcnow().date()

    return datetime.combine(
        selected_date,
        time.min,
    )


def end_of_day(target_date: date | None = None) -> datetime:
    """
    Return the beginning of the next date.

    This is useful for database filters using:

        value >= start
        value < end
    """

    return start_of_day(target_date) + timedelta(days=1)


def enum_value(value):
    """
    Convert an Enum instance to its string value.
    """

    if value is None:
        return None

    return value.value if hasattr(value, "value") else value

def get_delivery_or_404(
    db: Session,
    delivery_id: int,
) -> Delivery:
    delivery = (
        db.query(Delivery)
        .filter(Delivery.id == delivery_id)
        .first()
    )

    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery not found",
        )

    return delivery


def get_delivery_by_order_id(
    db: Session,
    order_id: int,
) -> Delivery | None:
    return (
        db.query(Delivery)
        .filter(Delivery.order_id == order_id)
        .first()
    )


def get_order_or_404(
    db: Session,
    order_id: int,
) -> Order:
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return order


def get_customer(
    db: Session,
    customer_id: int,
) -> User | None:
    return (
        db.query(User)
        .filter(User.id == customer_id)
        .first()
    )


def get_driver(
    db: Session,
    driver_id: int | None,
) -> User | None:
    if driver_id is None:
        return None

    return (
        db.query(User)
        .filter(
            User.id == driver_id,
            User.role == UserRole.DRIVER,
        )
        .first()
    )


def get_active_driver_or_404(
    db: Session,
    driver_id: int,
) -> User:
    driver = (
        db.query(User)
        .filter(
            User.id == driver_id,
            User.role == UserRole.DRIVER,
            User.is_active.is_(True),
        )
        .first()
    )

    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found or inactive",
        )

    return driver

def get_customer_active_driver_assignment(
    db: Session,
    customer_id: int,
) -> CustomerDriverAssignment | None:
    """
    Return the active dedicated-driver assignment for a customer.
    """

    return (
        db.query(CustomerDriverAssignment)
        .filter(
            CustomerDriverAssignment.customer_id == customer_id,
            CustomerDriverAssignment.is_active.is_(True),
        )
        .order_by(
            CustomerDriverAssignment.assigned_at.desc(),
            CustomerDriverAssignment.id.desc(),
        )
        .first()
    )


def get_customer_active_driver(
    db: Session,
    customer_id: int,
) -> User | None:
    """
    Return the active dedicated driver assigned to a customer.

    None is returned when:
    - the customer has no assignment;
    - the assigned account no longer exists;
    - the assigned user is not a driver;
    - the assigned driver is inactive.
    """

    assignment = get_customer_active_driver_assignment(
        db=db,
        customer_id=customer_id,
    )

    if not assignment:
        return None

    return (
        db.query(User)
        .filter(
            User.id == assignment.driver_id,
            User.role == UserRole.DRIVER,
            User.is_active.is_(True),
        )
        .first()
    )


def resolve_delivery_driver(
    db: Session,
    customer_id: int,
    requested_driver_id: int | None = None,
) -> User | None:
    """
    Resolve which driver should receive a delivery.

    Priority:
    1. Explicit driver chosen by an administrator.
    2. Customer's active dedicated driver.
    3. No driver, leaving the delivery pending.
    """

    if requested_driver_id is not None:
        return get_active_driver_or_404(
            db=db,
            driver_id=requested_driver_id,
        )

    return get_customer_active_driver(
        db=db,
        customer_id=customer_id,
    )


def ensure_order_has_no_delivery(
    db: Session,
    order_id: int,
) -> None:
    existing_delivery = get_delivery_by_order_id(
        db=db,
        order_id=order_id,
    )

    if existing_delivery:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery already exists for this order",
        )


def ensure_delivery_can_be_assigned(
    delivery: Delivery,
) -> None:
    blocked_statuses = {
        DeliveryStatus.PICKED_UP,
        DeliveryStatus.OUT_FOR_DELIVERY,
        DeliveryStatus.DELIVERED,
        DeliveryStatus.CANCELLED,
    }

    if delivery.status in blocked_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A driver cannot be assigned or changed while "
                f"the delivery status is {enum_value(delivery.status)}"
            ),
        )


def ensure_customer_can_access_delivery(
    delivery: Delivery,
    customer_id: int,
) -> None:
    if delivery.user_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to access this delivery",
        )


def ensure_driver_can_access_delivery(
    delivery: Delivery,
    driver_id: int,
) -> None:
    if delivery.driver_id != driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This delivery is not assigned to this driver",
        )


def create_delivery(
    db: Session,
    order_id: int,
) -> Delivery:
    """
    Create one delivery tracking record for an order.

    The customer, driver, delivery location, date, and time
    are already stored on the Order.
    """

    order = get_order_or_404(
        db=db,
        order_id=order_id,
    )

    existing_delivery = get_delivery_by_order_id(
        db=db,
        order_id=order.id,
    )

    if existing_delivery:
        return existing_delivery

    if order.driver_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order does not have an assigned driver",
        )

    if not order.delivery_address:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order does not have a delivery address",
        )

    if order.status not in {
        OrderStatus.CONFIRMED,
        OrderStatus.PREPARING,
        OrderStatus.READY_FOR_DELIVERY,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Delivery can only be created for a confirmed, "
                "preparing, or ready-for-delivery order"
            ),
        )

    delivery_status = DeliveryStatus.PENDING

    if order.status == OrderStatus.READY_FOR_DELIVERY:
        delivery_status = DeliveryStatus.READY_FOR_PICKUP

    delivery = Delivery(
        order_id=order.id,
        status=delivery_status,
        ready_for_pickup_at=(
            datetime.utcnow()
            if delivery_status
            == DeliveryStatus.READY_FOR_PICKUP
            else None
        ),
    )

    db.add(delivery)

    try:
        db.commit()
        db.refresh(delivery)

    except IntegrityError as exc:
        db.rollback()

        existing_delivery = get_delivery_by_order_id(
            db=db,
            order_id=order.id,
        )

        if existing_delivery:
            return existing_delivery

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery already exists for this order",
        ) from exc

    return delivery



def assign_driver_to_delivery(
    db: Session,
    delivery_id: int,
    driver_id: int,
) -> Delivery:
    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    ensure_delivery_can_be_assigned(delivery)

    driver = get_active_driver_or_404(
        db=db,
        driver_id=driver_id,
    )

    delivery.driver_id = driver.id
    delivery.status = DeliveryStatus.ASSIGNED
    delivery.failure_reason = None

    db.commit()
    db.refresh(delivery)

    return delivery


def assign_customer_dedicated_driver(
    db: Session,
    delivery_id: int,
) -> Delivery:
    """
    Assign the customer's current dedicated driver to a delivery.

    This can be used when a delivery was originally created without
    a driver and the customer received a driver assignment later.
    """

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    ensure_delivery_can_be_assigned(delivery)

    driver = get_customer_active_driver(
        db=db,
        customer_id=delivery.user_id,
    )

    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "The customer does not have an active "
                "dedicated driver"
            ),
        )

    delivery.driver_id = driver.id
    delivery.status = DeliveryStatus.ASSIGNED
    delivery.failure_reason = None

    db.commit()
    db.refresh(delivery)

    return delivery


def remove_driver_from_delivery(
    db: Session,
    delivery_id: int,
) -> Delivery:
    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    ensure_delivery_can_be_assigned(delivery)

    delivery.driver_id = None
    delivery.status = DeliveryStatus.PENDING
    delivery.failure_reason = None

    db.commit()
    db.refresh(delivery)

    return delivery

def cancel_delivery(
    db: Session,
    delivery_id: int,
    reason: str | None = None,
) -> Delivery:
    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    if delivery.status == DeliveryStatus.DELIVERED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A delivered delivery cannot be cancelled",
        )

    if delivery.status == DeliveryStatus.OUT_FOR_DELIVERY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A delivery that is already out for delivery "
                "cannot be cancelled from the operations endpoint"
            ),
        )

    if delivery.status == DeliveryStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Delivery is already cancelled",
        )

    delivery.status = DeliveryStatus.CANCELLED
    delivery.failure_reason = (
        reason.strip()
        if reason and reason.strip()
        else None
    )

    order = (
        db.query(Order)
        .filter(Order.id == delivery.order_id)
        .first()
    )

    if order:
        order.status = OrderStatus.CANCELLED

    db.commit()
    db.refresh(delivery)

    return delivery


def build_delivery_query(
    db: Session,
    search: str | None = None,
    delivery_status: DeliveryStatus | None = None,
    driver_id: int | None = None,
    customer_id: int | None = None,
    order_id: int | None = None,
    scheduled_date: date | None = None,
) -> Query:
    """
    Build the reusable admin delivery query.

    Search supports:
    - delivery address;
    - delivery notes;
    - failure reason;
    - customer first name;
    - customer last name;
    - customer email;
    - customer phone;
    - driver first name;
    - driver last name;
    - driver email;
    - driver phone;
    - order number.
    """

    query = (
        db.query(Delivery)
        .outerjoin(
            Order,
            Order.id == Delivery.order_id,
        )
        .outerjoin(
            User,
            User.id == Delivery.user_id,
        )
    )

    if search and search.strip():
        search_value = f"%{search.strip()}%"

        customer_user = User

        query = query.filter(
            or_(
                Delivery.delivery_address.ilike(search_value),
                Delivery.delivery_notes.ilike(search_value),
                Delivery.failure_reason.ilike(search_value),
                customer_user.first_name.ilike(search_value),
                customer_user.last_name.ilike(search_value),
                customer_user.email.ilike(search_value),
                customer_user.phone.ilike(search_value),
                Order.order_number.ilike(search_value),
            )
        )

    if delivery_status is not None:
        query = query.filter(
            Delivery.status == delivery_status
        )

    if driver_id is not None:
        query = query.filter(
            Delivery.driver_id == driver_id
        )

    if customer_id is not None:
        query = query.filter(
            Delivery.user_id == customer_id
        )

    if order_id is not None:
        query = query.filter(
            Delivery.order_id == order_id
        )

    if scheduled_date is not None:
        query = query.filter(
            Delivery.scheduled_at >= start_of_day(
                scheduled_date
            ),
            Delivery.scheduled_at < end_of_day(
                scheduled_date
            ),
        )

    return query.distinct()

def get_delivery_statistics(
    db: Session,
) -> dict:
    today_start = start_of_day()
    tomorrow_start = end_of_day()

    total = db.query(Delivery).count()

    pending = (
        db.query(Delivery)
        .filter(
            Delivery.status == DeliveryStatus.PENDING
        )
        .count()
    )

    assigned = (
        db.query(Delivery)
        .filter(
            Delivery.status == DeliveryStatus.ASSIGNED
        )
        .count()
    )

    picked_up = (
        db.query(Delivery)
        .filter(
            Delivery.status == DeliveryStatus.PICKED_UP
        )
        .count()
    )

    out_for_delivery = (
        db.query(Delivery)
        .filter(
            Delivery.status
            == DeliveryStatus.OUT_FOR_DELIVERY
        )
        .count()
    )

    delivered = (
        db.query(Delivery)
        .filter(
            Delivery.status == DeliveryStatus.DELIVERED
        )
        .count()
    )

    failed = (
        db.query(Delivery)
        .filter(
            Delivery.status == DeliveryStatus.FAILED
        )
        .count()
    )

    cancelled = (
        db.query(Delivery)
        .filter(
            Delivery.status == DeliveryStatus.CANCELLED
        )
        .count()
    )

    delivered_today = (
        db.query(Delivery)
        .filter(
            Delivery.status == DeliveryStatus.DELIVERED,
            Delivery.delivered_at >= today_start,
            Delivery.delivered_at < tomorrow_start,
        )
        .count()
    )

    failed_today = (
        db.query(Delivery)
        .filter(
            Delivery.status == DeliveryStatus.FAILED,
            Delivery.updated_at >= today_start,
            Delivery.updated_at < tomorrow_start,
        )
        .count()
    )

    scheduled_today = (
        db.query(Delivery)
        .filter(
            Delivery.scheduled_at >= today_start,
            Delivery.scheduled_at < tomorrow_start,
        )
        .count()
    )

    working_drivers = (
        db.query(Delivery.driver_id)
        .filter(
            Delivery.driver_id.isnot(None),
            Delivery.status.in_(
                [
                    DeliveryStatus.PICKED_UP,
                    DeliveryStatus.OUT_FOR_DELIVERY,
                ]
            ),
        )
        .distinct()
        .count()
    )

    active_deliveries = (
        pending
        + assigned
        + picked_up
        + out_for_delivery
    )

    completion_rate = (
        round((delivered / total) * 100, 2)
        if total
        else 0.0
    )

    failure_rate = (
        round((failed / total) * 100, 2)
        if total
        else 0.0
    )

    return {
        "total": total,
        "active": active_deliveries,
        "pending": pending,
        "assigned": assigned,
        "picked_up": picked_up,
        "out_for_delivery": out_for_delivery,
        "delivered": delivered,
        "failed": failed,
        "cancelled": cancelled,
        "scheduled_today": scheduled_today,
        "delivered_today": delivered_today,
        "failed_today": failed_today,
        "working_drivers": working_drivers,
        "completion_rate": completion_rate,
        "failure_rate": failure_rate,
    }