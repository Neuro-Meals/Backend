from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session, aliased

from app.modules.customer_drivers.models import (
    CustomerDriverAssignment,
)
from app.modules.deliveries.models import (
    Delivery,
    DeliveryStatus,
)
from app.modules.orders.models import (
    Order,
    OrderStatus,
)
from app.modules.users.models import (
    User,
    UserRole,
)


def utc_now() -> datetime:
    """
    Return the current UTC datetime.

    The project currently uses naive UTC datetimes.
    """

    return datetime.utcnow()


def start_of_day(
    target_date: date | None = None,
) -> datetime:
    """
    Return the beginning of the selected UTC date.
    """

    selected_date = target_date or utc_now().date()

    return datetime.combine(
        selected_date,
        time.min,
    )


def end_of_day(
    target_date: date | None = None,
) -> datetime:
    """
    Return the beginning of the next UTC date.
    """

    return start_of_day(target_date) + timedelta(days=1)


def enum_value(value):
    """
    Convert an Enum instance to its string value.
    """

    if value is None:
        return None

    return value.value if hasattr(value, "value") else value

def get_delivery_for_order(
    db: Session,
    order_id: int,
) -> Delivery | None:
    """
    Return the delivery tracking record for an order.
    """

    return (
        db.query(Delivery)
        .filter(Delivery.order_id == order_id)
        .first()
    )


def get_delivery_by_order_id(
    db: Session,
    order_id: int,
) -> Delivery | None:
    """
    Backward-compatible alias for get_delivery_for_order().
    """

    return get_delivery_for_order(
        db=db,
        order_id=order_id,
    )


def get_delivery_or_404(
    db: Session,
    delivery_id: int,
) -> Delivery:
    """
    Return a delivery or raise HTTP 404.
    """

    delivery = (
        db.query(Delivery)
        .filter(Delivery.id == delivery_id)
        .first()
    )

    if delivery is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery not found",
        )

    return delivery


def get_order_or_404(
    db: Session,
    order_id: int,
) -> Order:
    """
    Return an order or raise HTTP 404.
    """

    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return order


def get_order_for_delivery(
    db: Session,
    delivery: Delivery,
) -> Order:
    """
    Return the Order connected to a Delivery.
    """

    if delivery.order is not None:
        return delivery.order

    return get_order_or_404(
        db=db,
        order_id=delivery.order_id,
    )

def get_customer(
    db: Session,
    customer_id: int,
) -> User | None:
    """
    Return a customer account by ID.
    """

    return (
        db.query(User)
        .filter(User.id == customer_id)
        .first()
    )


def get_driver(
    db: Session,
    driver_id: int | None,
) -> User | None:
    """
    Return a driver account by ID.
    """

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
    """
    Return an active driver or raise HTTP 404.
    """

    driver = (
        db.query(User)
        .filter(
            User.id == driver_id,
            User.role == UserRole.DRIVER,
            User.is_active.is_(True),
        )
        .first()
    )

    if driver is None:
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
    Return the latest active dedicated-driver assignment
    for a customer.
    """

    return (
        db.query(CustomerDriverAssignment)
        .filter(
            CustomerDriverAssignment.customer_id
            == customer_id,
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
    Return the customer's active dedicated driver.
    """

    assignment = get_customer_active_driver_assignment(
        db=db,
        customer_id=customer_id,
    )

    if assignment is None:
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
    Resolve a driver using this priority:

    1. Explicitly requested driver.
    2. Customer's active dedicated driver.
    3. No driver.
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
    """
    Ensure that an order does not already have a delivery.
    """

    existing_delivery = get_delivery_for_order(
        db=db,
        order_id=order_id,
    )

    if existing_delivery is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery already exists for this order",
        )


def ensure_order_can_create_delivery(
    order: Order,
) -> None:
    """
    Validate that an order has the data required to create
    a delivery tracking record.
    """

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

    allowed_statuses = {
        OrderStatus.CONFIRMED,
        OrderStatus.PREPARING,
        OrderStatus.READY_FOR_DELIVERY,
    }

    if order.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Delivery can only be created for a confirmed, "
                "preparing, or ready-for-delivery order"
            ),
        )


def ensure_delivery_can_be_assigned(
    delivery: Delivery,
) -> None:
    """
    Ensure the order's driver may still be changed.
    """

    blocked_statuses = {
        DeliveryStatus.PICKED_UP,
        DeliveryStatus.OUT_FOR_DELIVERY,
        DeliveryStatus.DELIVERED,
        DeliveryStatus.CANCELLED,
    }

    if delivery.status in blocked_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The driver cannot be changed while delivery "
                f"status is {enum_value(delivery.status)}"
            ),
        )


def ensure_customer_can_access_delivery(
    delivery: Delivery,
    customer_id: int,
) -> None:
    """
    Ensure the customer owns the Order connected to the Delivery.
    """

    if delivery.order is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Delivery order relationship is unavailable",
        )

    if delivery.order.user_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to access this delivery",
        )


def ensure_driver_can_access_delivery(
    delivery: Delivery,
    driver_id: int,
) -> None:
    """
    Ensure the driver is assigned to the connected Order.
    """

    if delivery.order is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Delivery order relationship is unavailable",
        )

    if delivery.order.driver_id != driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This delivery is not assigned to this driver",
        )


def ensure_delivery_status(
    delivery: Delivery,
    allowed_statuses: set[DeliveryStatus],
    detail: str,
) -> None:
    """
    Ensure a Delivery currently has one of the allowed statuses.
    """

    if delivery.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )

def ensure_delivery_for_order(
    db: Session,
    order: Order,
    *,
    commit: bool = False,
) -> Delivery:
    """
    Create one Delivery tracking row for an Order.

    If the Delivery already exists, return it.

    When the Order is READY_FOR_DELIVERY, the Delivery becomes
    READY_FOR_PICKUP.

    Use commit=False when this function is called inside another
    transaction, such as the Chef ready endpoint.
    """

    existing = get_delivery_for_order(
        db=db,
        order_id=order.id,
    )

    if existing is not None:
        if (
            order.status == OrderStatus.READY_FOR_DELIVERY
            and existing.status == DeliveryStatus.PENDING
        ):
            existing.status = DeliveryStatus.READY_FOR_PICKUP
            existing.ready_for_pickup_at = (
                existing.ready_for_pickup_at
                or utc_now()
            )
            existing.failure_reason = None
            existing.failed_at = None

        if commit:
            try:
                db.commit()
                db.refresh(existing)
            except Exception:
                db.rollback()
                raise

        return existing

    ensure_order_can_create_delivery(order)

    initial_status = DeliveryStatus.PENDING
    ready_for_pickup_at = None

    if order.status == OrderStatus.READY_FOR_DELIVERY:
        initial_status = DeliveryStatus.READY_FOR_PICKUP
        ready_for_pickup_at = utc_now()

    delivery = Delivery(
        order_id=order.id,
        status=initial_status,
        ready_for_pickup_at=ready_for_pickup_at,
    )

    try:
        # A nested transaction prevents a unique-constraint failure
        # from rolling back other changes in the caller's transaction.
        with db.begin_nested():
            db.add(delivery)
            db.flush()

    except IntegrityError:
        existing = get_delivery_for_order(
            db=db,
            order_id=order.id,
        )

        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Delivery already exists for this order",
            )

        delivery = existing

    if commit:
        try:
            db.commit()
            db.refresh(delivery)
        except Exception:
            db.rollback()
            raise

    return delivery


def create_delivery(
    db: Session,
    order_id: int,
) -> Delivery:
    """
    Create a delivery tracking record for an existing Order.
    """

    order = get_order_or_404(
        db=db,
        order_id=order_id,
    )

    return ensure_delivery_for_order(
        db=db,
        order=order,
        commit=True,
    )

def assign_driver_to_delivery(
    db: Session,
    delivery_id: int,
    driver_id: int,
) -> Delivery:
    """
    Change the driver stored on the connected Order.

    Delivery does not contain driver_id. Driver assignment belongs
    to Order.
    """

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    ensure_delivery_can_be_assigned(delivery)

    driver = get_active_driver_or_404(
        db=db,
        driver_id=driver_id,
    )

    order = get_order_for_delivery(
        db=db,
        delivery=delivery,
    )

    order.driver_id = driver.id

    delivery.failure_reason = None
    delivery.failed_at = None

    if (
        order.status == OrderStatus.READY_FOR_DELIVERY
        and delivery.status
        in {
            DeliveryStatus.PENDING,
            DeliveryStatus.FAILED,
        }
    ):
        delivery.status = DeliveryStatus.READY_FOR_PICKUP
        delivery.ready_for_pickup_at = (
            delivery.ready_for_pickup_at
            or utc_now()
        )

    try:
        db.commit()
        db.refresh(delivery)
    except Exception:
        db.rollback()
        raise

    return delivery


def assign_customer_dedicated_driver(
    db: Session,
    delivery_id: int,
) -> Delivery:
    """
    Assign the customer's current dedicated driver to the
    connected Order.
    """

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    ensure_delivery_can_be_assigned(delivery)

    order = get_order_for_delivery(
        db=db,
        delivery=delivery,
    )

    driver = get_customer_active_driver(
        db=db,
        customer_id=order.user_id,
    )

    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "The customer does not have an active "
                "dedicated driver"
            ),
        )

    order.driver_id = driver.id

    delivery.failure_reason = None
    delivery.failed_at = None

    if (
        order.status == OrderStatus.READY_FOR_DELIVERY
        and delivery.status
        in {
            DeliveryStatus.PENDING,
            DeliveryStatus.FAILED,
        }
    ):
        delivery.status = DeliveryStatus.READY_FOR_PICKUP
        delivery.ready_for_pickup_at = (
            delivery.ready_for_pickup_at
            or utc_now()
        )

    try:
        db.commit()
        db.refresh(delivery)
    except Exception:
        db.rollback()
        raise

    return delivery


def remove_driver_from_delivery(
    db: Session,
    delivery_id: int,
) -> Delivery:
    """
    Driver removal is not supported because Order.driver_id is
    non-nullable.

    Use assign_driver_to_delivery() to replace the driver.
    """

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    ensure_delivery_can_be_assigned(delivery)

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "A driver cannot be removed because every order "
            "requires a driver. Assign a different driver instead."
        ),
    )

def mark_delivery_ready_for_pickup(
    db: Session,
    delivery_id: int,
) -> Delivery:
    """
    Mark a Delivery as ready for driver pickup.
    """

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    order = get_order_for_delivery(
        db=db,
        delivery=delivery,
    )

    ensure_delivery_status(
        delivery=delivery,
        allowed_statuses={
            DeliveryStatus.PENDING,
            DeliveryStatus.FAILED,
        },
        detail=(
            "Only pending or failed deliveries can be marked "
            "ready for pickup"
        ),
    )

    if order.status != OrderStatus.READY_FOR_DELIVERY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The order must be ready for delivery before "
                "pickup can begin"
            ),
        )

    delivery.status = DeliveryStatus.READY_FOR_PICKUP
    delivery.ready_for_pickup_at = utc_now()
    delivery.failed_at = None
    delivery.failure_reason = None

    try:
        db.commit()
        db.refresh(delivery)
    except Exception:
        db.rollback()
        raise

    return delivery


def mark_delivery_picked_up(
    db: Session,
    delivery_id: int,
) -> Delivery:
    """
    Mark food as collected by the assigned driver.
    """

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    order = get_order_for_delivery(
        db=db,
        delivery=delivery,
    )

    ensure_delivery_status(
        delivery=delivery,
        allowed_statuses={
            DeliveryStatus.READY_FOR_PICKUP,
        },
        detail=(
            "Only a delivery that is ready for pickup "
            "can be picked up"
        ),
    )

    if order.status != OrderStatus.READY_FOR_DELIVERY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The order is not ready for delivery",
        )

    delivery.status = DeliveryStatus.PICKED_UP
    delivery.picked_up_at = utc_now()
    delivery.failure_reason = None
    delivery.failed_at = None

    try:
        db.commit()
        db.refresh(delivery)
    except Exception:
        db.rollback()
        raise

    return delivery


def mark_delivery_out_for_delivery(
    db: Session,
    delivery_id: int,
) -> Delivery:
    """
    Mark a picked-up Delivery as out for delivery.

    The connected Order is updated at the same time.
    """

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    ensure_delivery_status(
        delivery=delivery,
        allowed_statuses={
            DeliveryStatus.PICKED_UP,
        },
        detail=(
            "Only a picked-up delivery can be marked "
            "out for delivery"
        ),
    )

    order = get_order_for_delivery(
        db=db,
        delivery=delivery,
    )

    timestamp = utc_now()

    delivery.status = DeliveryStatus.OUT_FOR_DELIVERY
    delivery.out_for_delivery_at = timestamp
    delivery.failure_reason = None
    delivery.failed_at = None

    order.status = OrderStatus.OUT_FOR_DELIVERY
    order.out_for_delivery_at = timestamp

    try:
        db.commit()
        db.refresh(delivery)
    except Exception:
        db.rollback()
        raise

    return delivery


def mark_delivery_delivered(
    db: Session,
    delivery_id: int,
) -> Delivery:
    """
    Complete a Delivery and its connected Order.
    """

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    ensure_delivery_status(
        delivery=delivery,
        allowed_statuses={
            DeliveryStatus.OUT_FOR_DELIVERY,
        },
        detail=(
            "Only an out-for-delivery delivery can be "
            "marked delivered"
        ),
    )

    order = get_order_for_delivery(
        db=db,
        delivery=delivery,
    )

    timestamp = utc_now()

    delivery.status = DeliveryStatus.DELIVERED
    delivery.delivered_at = timestamp
    delivery.failure_reason = None
    delivery.failed_at = None

    order.status = OrderStatus.DELIVERED
    order.delivered_at = timestamp

    try:
        db.commit()
        db.refresh(delivery)
    except Exception:
        db.rollback()
        raise

    return delivery


def mark_delivery_failed(
    db: Session,
    delivery_id: int,
    reason: str,
) -> Delivery:
    """
    Mark an active delivery attempt as failed.

    The Order returns to READY_FOR_DELIVERY so another delivery
    attempt can be made.
    """

    clean_reason = reason.strip()

    if len(clean_reason) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failure reason must contain at least 3 characters",
        )

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    ensure_delivery_status(
        delivery=delivery,
        allowed_statuses={
            DeliveryStatus.READY_FOR_PICKUP,
            DeliveryStatus.PICKED_UP,
            DeliveryStatus.OUT_FOR_DELIVERY,
        },
        detail=(
            "Only an active delivery can be marked as failed"
        ),
    )

    order = get_order_for_delivery(
        db=db,
        delivery=delivery,
    )

    delivery.status = DeliveryStatus.FAILED
    delivery.failed_at = utc_now()
    delivery.failure_reason = clean_reason[:500]

    order.status = OrderStatus.READY_FOR_DELIVERY
    order.out_for_delivery_at = None

    try:
        db.commit()
        db.refresh(delivery)
    except Exception:
        db.rollback()
        raise

    return delivery


def retry_failed_delivery(
    db: Session,
    delivery_id: int,
) -> Delivery:
    """
    Return a failed Delivery to READY_FOR_PICKUP.
    """

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    ensure_delivery_status(
        delivery=delivery,
        allowed_statuses={
            DeliveryStatus.FAILED,
        },
        detail="Only a failed delivery can be retried",
    )

    order = get_order_for_delivery(
        db=db,
        delivery=delivery,
    )

    if order.status != OrderStatus.READY_FOR_DELIVERY:
        order.status = OrderStatus.READY_FOR_DELIVERY

    delivery.status = DeliveryStatus.READY_FOR_PICKUP
    delivery.ready_for_pickup_at = utc_now()
    delivery.picked_up_at = None
    delivery.out_for_delivery_at = None
    delivery.delivered_at = None
    delivery.failed_at = None
    delivery.failure_reason = None

    try:
        db.commit()
        db.refresh(delivery)
    except Exception:
        db.rollback()
        raise

    return delivery


def cancel_delivery(
    db: Session,
    delivery_id: int,
    reason: str | None = None,
) -> Delivery:
    """
    Cancel a Delivery and its connected Order.
    """

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    if delivery.status == DeliveryStatus.DELIVERED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A delivered delivery cannot be cancelled",
        )

    if delivery.status == DeliveryStatus.OUT_FOR_DELIVERY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A delivery that is out for delivery cannot "
                "be cancelled from this operation"
            ),
        )

    if delivery.status == DeliveryStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery is already cancelled",
        )

    order = get_order_for_delivery(
        db=db,
        delivery=delivery,
    )

    timestamp = utc_now()
    clean_reason = (
        reason.strip()
        if reason and reason.strip()
        else None
    )

    delivery.status = DeliveryStatus.CANCELLED
    delivery.cancelled_at = timestamp
    delivery.failure_reason = clean_reason

    order.status = OrderStatus.CANCELLED
    order.cancelled_at = timestamp
    order.cancellation_reason = clean_reason

    try:
        db.commit()
        db.refresh(delivery)
    except Exception:
        db.rollback()
        raise

    return delivery

def update_driver_location(
    db: Session,
    delivery_id: int,
    latitude: float,
    longitude: float,
) -> Delivery:
    """
    Update the driver's current location during an active delivery.
    """

    if latitude < -90 or latitude > 90:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Latitude must be between -90 and 90",
        )

    if longitude < -180 or longitude > 180:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Longitude must be between -180 and 180",
        )

    delivery = get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    ensure_delivery_status(
        delivery=delivery,
        allowed_statuses={
            DeliveryStatus.PICKED_UP,
            DeliveryStatus.OUT_FOR_DELIVERY,
        },
        detail=(
            "Driver location can only be updated after pickup "
            "and before delivery completion"
        ),
    )

    delivery.current_latitude = latitude
    delivery.current_longitude = longitude

    try:
        db.commit()
        db.refresh(delivery)
    except Exception:
        db.rollback()
        raise

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
    Build a reusable Delivery query.

    Business fields are read from Order because Delivery contains
    tracking fields only.

    Search supports:

    - delivery address
    - delivery notes
    - delivery place name
    - delivery city
    - delivery area
    - failure reason
    - order number
    - customer name, email, and phone
    - driver name, email, and phone
    """

    customer_user = aliased(User)
    driver_user = aliased(User)

    query = (
        db.query(Delivery)
        .join(
            Order,
            Order.id == Delivery.order_id,
        )
        .outerjoin(
            customer_user,
            customer_user.id == Order.user_id,
        )
        .outerjoin(
            driver_user,
            driver_user.id == Order.driver_id,
        )
    )

    if search and search.strip():
        search_value = f"%{search.strip()}%"

        query = query.filter(
            or_(
                Order.order_number.ilike(search_value),
                Order.delivery_address.ilike(search_value),
                Order.delivery_notes.ilike(search_value),
                Order.delivery_place_name.ilike(search_value),
                Order.delivery_city.ilike(search_value),
                Order.delivery_area.ilike(search_value),
                Delivery.failure_reason.ilike(search_value),
                customer_user.first_name.ilike(search_value),
                customer_user.last_name.ilike(search_value),
                customer_user.email.ilike(search_value),
                customer_user.phone.ilike(search_value),
                driver_user.first_name.ilike(search_value),
                driver_user.last_name.ilike(search_value),
                driver_user.email.ilike(search_value),
                driver_user.phone.ilike(search_value),
            )
        )

    if delivery_status is not None:
        query = query.filter(
            Delivery.status == delivery_status
        )

    if driver_id is not None:
        query = query.filter(
            Order.driver_id == driver_id
        )

    if customer_id is not None:
        query = query.filter(
            Order.user_id == customer_id
        )

    if order_id is not None:
        query = query.filter(
            Delivery.order_id == order_id
        )

    if scheduled_date is not None:
        query = query.filter(
            Order.delivery_date == scheduled_date
        )

    return query.distinct()


def build_driver_delivery_query(
    db: Session,
    driver_id: int,
    target_date: date | None = None,
) -> Query:
    """
    Return deliveries assigned to a driver through Order.driver_id.
    """

    query = (
        db.query(Delivery)
        .join(
            Order,
            Order.id == Delivery.order_id,
        )
        .filter(
            Order.driver_id == driver_id,
        )
    )

    if target_date is not None:
        query = query.filter(
            Order.delivery_date == target_date
        )

    return query


def get_driver_deliveries_for_date(
    db: Session,
    driver_id: int,
    target_date: date,
) -> list[Delivery]:
    """
    Return a driver's deliveries for one delivery date.
    """

    return (
        build_driver_delivery_query(
            db=db,
            driver_id=driver_id,
            target_date=target_date,
        )
        .order_by(
            Order.delivery_time.asc(),
            Delivery.id.asc(),
        )
        .all()
    )


def get_driver_today_deliveries(
    db: Session,
    driver_id: int,
) -> list[Delivery]:
    """
    Return today's deliveries for a driver.
    """

    return get_driver_deliveries_for_date(
        db=db,
        driver_id=driver_id,
        target_date=utc_now().date(),
    )


def get_driver_tomorrow_deliveries(
    db: Session,
    driver_id: int,
) -> list[Delivery]:
    """
    Return tomorrow's deliveries for a driver.
    """

    tomorrow = utc_now().date() + timedelta(days=1)

    return get_driver_deliveries_for_date(
        db=db,
        driver_id=driver_id,
        target_date=tomorrow,
    )


def get_driver_delivery_history(
    db: Session,
    driver_id: int,
) -> list[Delivery]:
    """
    Return completed, failed, and cancelled driver deliveries.
    """

    return (
        build_driver_delivery_query(
            db=db,
            driver_id=driver_id,
        )
        .filter(
            Delivery.status.in_(
                {
                    DeliveryStatus.DELIVERED,
                    DeliveryStatus.FAILED,
                    DeliveryStatus.CANCELLED,
                }
            )
        )
        .order_by(
            Order.delivery_date.desc(),
            Order.delivery_time.desc(),
            Delivery.id.desc(),
        )
        .all()
    )

def get_delivery_statistics(
    db: Session,
) -> dict:
    """
    Return delivery operations statistics.

    The old 'assigned' key is retained for frontend compatibility.
    It represents deliveries attached to an Order with a driver
    that have not yet been picked up.
    """

    today = utc_now().date()
    today_start = start_of_day(today)
    tomorrow_start = end_of_day(today)

    total = db.query(Delivery).count()

    pending = (
        db.query(Delivery)
        .filter(
            Delivery.status == DeliveryStatus.PENDING
        )
        .count()
    )

    ready_for_pickup = (
        db.query(Delivery)
        .filter(
            Delivery.status
            == DeliveryStatus.READY_FOR_PICKUP
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

    scheduled_today = (
        db.query(Delivery)
        .join(
            Order,
            Order.id == Delivery.order_id,
        )
        .filter(
            Order.delivery_date == today
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
            Delivery.failed_at >= today_start,
            Delivery.failed_at < tomorrow_start,
        )
        .count()
    )

    working_drivers = (
        db.query(Order.driver_id)
        .join(
            Delivery,
            Delivery.order_id == Order.id,
        )
        .filter(
            Order.driver_id.isnot(None),
            Delivery.status.in_(
                {
                    DeliveryStatus.PICKED_UP,
                    DeliveryStatus.OUT_FOR_DELIVERY,
                }
            ),
        )
        .distinct()
        .count()
    )

    assigned = pending + ready_for_pickup

    active_deliveries = (
        pending
        + ready_for_pickup
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
        "ready_for_pickup": ready_for_pickup,
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
    
    