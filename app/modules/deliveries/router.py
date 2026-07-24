from __future__ import annotations

from datetime import datetime, time
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.common.exceptions import (
    BadRequestException,
    DeliveryAlreadyExistsException,
    DeliveryNotFoundException,
    DriverNotFoundException,
    ForbiddenException,
    MissingDeliveryAddressException,
    OrderNotFoundException,
)
from app.common.responses import (
    created_response,
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
from app.modules.deliveries.models import (
    Delivery,
    DeliveryStatus,
)
from app.modules.deliveries.schemas import (
    AssignDriverRequest,
    DeliveryCreate,
)
from app.modules.orders.models import (
    Order,
    OrderStatus,
)
from app.modules.users.models import (
    User,
    UserRole,
)


router = APIRouter(
    prefix="/deliveries",
    tags=["Deliveries"],
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


def _get_delivery_or_404(
    db: Session,
    delivery_id: int,
) -> Delivery:
    delivery = (
        db.query(Delivery)
        .filter(Delivery.id == delivery_id)
        .first()
    )

    if delivery is None:
        raise DeliveryNotFoundException()

    return delivery


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


def _get_active_driver_or_404(
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

    if driver is None:
        raise DriverNotFoundException(
            "Driver not found or inactive."
        )

    return driver


def _is_management_user(user: User) -> bool:
    return user.role in {
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN,
        UserRole.DELIVERY_MANAGER,
    }


def _ensure_delivery_access(
    delivery: Delivery,
    current_user: User,
) -> None:
    if _is_management_user(current_user):
        return

    if (
        current_user.role == UserRole.CUSTOMER
        and delivery.user_id == current_user.id
    ):
        return

    if (
        current_user.role == UserRole.DRIVER
        and delivery.driver_id == current_user.id
    ):
        return

    raise ForbiddenException(
        "You are not allowed to access this delivery."
    )

def _extract_order_items(order: Order | None) -> list[dict]:
    if order is None:
        return []

    raw_items = getattr(order, "items", None)

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


def _build_meal_information(
    order: Order | None,
) -> dict[str, Any]:
    items = _extract_order_items(order)

    meal_count = 0
    meal_names: list[str] = []

    for item in items:
        raw_quantity = item.get("quantity", 1)

        try:
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            quantity = 1

        quantity = max(quantity, 1)
        meal_count += quantity

        meal_name = (
            item.get("meal_name")
            or item.get("name")
            or item.get("name_en")
        )

        if meal_name:
            formatted_name = str(meal_name)

            if quantity > 1:
                formatted_name = (
                    f"{formatted_name} x{quantity}"
                )

            meal_names.append(formatted_name)

    visible_names = meal_names[:3]
    remaining_count = len(meal_names) - len(visible_names)

    meal_summary = ", ".join(visible_names)

    if remaining_count > 0:
        meal_summary = (
            f"{meal_summary} +{remaining_count}"
        )

    return {
        "meal_count": meal_count,
        "meal_summary": meal_summary,
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


def _build_order_summary(
    order: Order | None,
) -> dict[str, Any] | None:
    if order is None:
        return None

    return {
        "id": order.id,
        "order_number": getattr(
            order,
            "order_number",
            None,
        ),
        "status": _enum_value(
            getattr(order, "status", None)
        ),
        "total_amount": getattr(
            order,
            "total_amount",
            None,
        ),
        "delivery_date": getattr(
            order,
            "delivery_date",
            None,
        ),
        "items": getattr(order, "items", None),
    }


def _build_delivery_response(
    delivery: Delivery,
    *,
    customer: User | None = None,
    driver: User | None = None,
    order: Order | None = None,
) -> dict[str, Any]:
    meal_information = _build_meal_information(order)

    return {
        "id": delivery.id,
        "order_id": delivery.order_id,
        "user_id": delivery.user_id,
        "driver_id": delivery.driver_id,
        "status": _enum_value(delivery.status),
        "delivery_address": (
            delivery.delivery_address
        ),
        "delivery_notes": delivery.delivery_notes,
        "scheduled_at": delivery.scheduled_at,
        "picked_up_at": delivery.picked_up_at,
        "delivered_at": delivery.delivered_at,
        "current_latitude": (
            delivery.current_latitude
        ),
        "current_longitude": (
            delivery.current_longitude
        ),
        "failure_reason": delivery.failure_reason,
        "created_at": delivery.created_at,
        "updated_at": delivery.updated_at,
        "customer": _build_customer_summary(
            customer
        ),
        "driver": _build_driver_summary(driver),
        "order": _build_order_summary(order),
        "meal_count": meal_information[
            "meal_count"
        ],
        "meal_summary": meal_information[
            "meal_summary"
        ],
        "timeline": {
            "created_at": delivery.created_at,
            "scheduled_at": delivery.scheduled_at,
            "picked_up_at": delivery.picked_up_at,
            "delivered_at": delivery.delivered_at,
            "updated_at": delivery.updated_at,
        },
        "location": {
            "latitude": delivery.current_latitude,
            "longitude": (
                delivery.current_longitude
            ),
        },
    }


def _load_related_records(
    db: Session,
    deliveries: list[Delivery],
) -> tuple[
    dict[int, User],
    dict[int, User],
    dict[int, Order],
]:
    customer_ids = {
        delivery.user_id
        for delivery in deliveries
        if delivery.user_id is not None
    }

    driver_ids = {
        delivery.driver_id
        for delivery in deliveries
        if delivery.driver_id is not None
    }

    order_ids = {
        delivery.order_id
        for delivery in deliveries
        if delivery.order_id is not None
    }

    customer_map: dict[int, User] = {}
    driver_map: dict[int, User] = {}
    order_map: dict[int, Order] = {}

    if customer_ids:
        customers = (
            db.query(User)
            .filter(User.id.in_(customer_ids))
            .all()
        )

        customer_map = {
            customer.id: customer
            for customer in customers
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

    if order_ids:
        orders = (
            db.query(Order)
            .filter(Order.id.in_(order_ids))
            .all()
        )

        order_map = {
            order.id: order
            for order in orders
        }

    return customer_map, driver_map, order_map


def _serialize_delivery_list(
    db: Session,
    deliveries: list[Delivery],
) -> list[dict[str, Any]]:
    customer_map, driver_map, order_map = (
        _load_related_records(
            db,
            deliveries,
        )
    )

    return [
        _build_delivery_response(
            delivery,
            customer=customer_map.get(
                delivery.user_id
            ),
            driver=driver_map.get(
                delivery.driver_id
            ),
            order=order_map.get(
                delivery.order_id
            ),
        )
        for delivery in deliveries
    ]

@router.post("/")
def create_delivery(
    payload: DeliveryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    order = _get_order_or_404(
        db,
        payload.order_id,
    )

    existing_delivery = (
        db.query(Delivery)
        .filter(Delivery.order_id == order.id)
        .first()
    )

    if existing_delivery is not None:
        raise DeliveryAlreadyExistsException()

    driver = None

    if payload.driver_id is not None:
        driver = _get_active_driver_or_404(
            db,
            payload.driver_id,
        )

    delivery_address = (
        payload.delivery_address
        or getattr(order, "delivery_address", None)
    )

    if not delivery_address:
        raise MissingDeliveryAddressException()

    delivery = Delivery(
        order_id=order.id,
        user_id=order.user_id,
        driver_id=(
            driver.id
            if driver is not None
            else None
        ),
        status=(
            DeliveryStatus.ASSIGNED
            if driver is not None
            else DeliveryStatus.PENDING
        ),
        delivery_address=delivery_address,
        delivery_notes=(
            payload.delivery_notes
            or getattr(
                order,
                "delivery_notes",
                None,
            )
        ),
        scheduled_at=payload.scheduled_at,
    )

    try:
        db.add(delivery)
        order.status = (
            OrderStatus.READY_FOR_DELIVERY
        )

        db.commit()
        db.refresh(delivery)

    except Exception:
        db.rollback()
        raise

    customer = (
        db.query(User)
        .filter(User.id == delivery.user_id)
        .first()
    )

    return created_response(
        data=_build_delivery_response(
            delivery,
            customer=customer,
            driver=driver,
            order=order,
        ),
        message="Delivery created successfully.",
    )

@router.get("/dashboard")
def delivery_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    status_rows = (
        db.query(
            Delivery.status,
            Delivery.id,
        )
        .all()
    )

    status_counts: dict[str, int] = {}

    for status_value, _delivery_id in status_rows:
        key = str(_enum_value(status_value))

        status_counts[key] = (
            status_counts.get(key, 0) + 1
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

    total_deliveries = len(status_rows)

    scheduled_today = (
        db.query(Delivery)
        .filter(
            Delivery.scheduled_at >= today_start,
            Delivery.scheduled_at <= today_end,
        )
        .count()
    )

    delivered_today = (
        db.query(Delivery)
        .filter(
            Delivery.delivered_at >= today_start,
            Delivery.delivered_at <= today_end,
        )
        .count()
    )

    unassigned_deliveries = (
        db.query(Delivery)
        .filter(Delivery.driver_id.is_(None))
        .count()
    )

    recent_deliveries = (
        db.query(Delivery)
        .order_by(Delivery.id.desc())
        .limit(10)
        .all()
    )

    return dashboard_response(
        overview={
            "total_deliveries": total_deliveries,
            "scheduled_today": scheduled_today,
            "delivered_today": delivered_today,
            "unassigned_deliveries": (
                unassigned_deliveries
            ),
        },
        statistics={
            "by_status": status_counts,
        },
        recent_activity=_serialize_delivery_list(
            db,
            recent_deliveries,
        ),
    )

@router.get("/")
def list_deliveries(
    search: str | None = Query(
        default=None,
        min_length=1,
    ),
    delivery_status: DeliveryStatus | None = Query(
        default=None,
        alias="status",
    ),
    driver_id: int | None = Query(
        default=None,
        ge=1,
    ),
    user_id: int | None = Query(
        default=None,
        ge=1,
    ),
    order_id: int | None = Query(
        default=None,
        ge=1,
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
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    query = db.query(Delivery)

    if search:
        search_value = f"%{search.strip()}%"

        query = (
            query.outerjoin(
                Order,
                Order.id == Delivery.order_id,
            )
            .outerjoin(
                User,
                User.id == Delivery.user_id,
            )
            .filter(
                or_(
                    Delivery.delivery_address.ilike(
                        search_value
                    ),
                    Delivery.delivery_notes.ilike(
                        search_value
                    ),
                    Delivery.failure_reason.ilike(
                        search_value
                    ),
                    Order.order_number.ilike(
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

    if delivery_status is not None:
        query = query.filter(
            Delivery.status == delivery_status
        )

    if driver_id is not None:
        query = query.filter(
            Delivery.driver_id == driver_id
        )

    if user_id is not None:
        query = query.filter(
            Delivery.user_id == user_id
        )

    if order_id is not None:
        query = query.filter(
            Delivery.order_id == order_id
        )

    total = query.count()

    deliveries = (
        query.order_by(Delivery.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return list_response(
        items=_serialize_delivery_list(
            db,
            deliveries,
        ),
        page=page,
        limit=limit,
        total=total,
        message="Deliveries retrieved successfully.",
    )

@router.get("/my")
def my_deliveries(
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
        db.query(Delivery)
        .filter(
            Delivery.user_id == current_user.id
        )
    )

    total = query.count()

    deliveries = (
        query.order_by(Delivery.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return list_response(
        items=_serialize_delivery_list(
            db,
            deliveries,
        ),
        page=page,
        limit=limit,
        total=total,
        message=(
            "Your deliveries were retrieved "
            "successfully."
        ),
    )

@router.get("/customer/{customer_id}/history")
def customer_delivery_history(
    customer_id: int,
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
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
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
        raise BadRequestException(
            "Customer not found."
        )

    query = (
        db.query(Delivery)
        .filter(
            Delivery.user_id == customer_id
        )
    )

    total = query.count()

    deliveries = (
        query.order_by(Delivery.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return list_response(
        items=_serialize_delivery_list(
            db,
            deliveries,
        ),
        page=page,
        limit=limit,
        total=total,
        message=(
            "Customer delivery history retrieved "
            "successfully."
        ),
    )

@router.get("/{delivery_id}")
def get_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    delivery = _get_delivery_or_404(
        db,
        delivery_id,
    )

    _ensure_delivery_access(
        delivery,
        current_user,
    )

    customer = (
        db.query(User)
        .filter(User.id == delivery.user_id)
        .first()
    )

    driver = None

    if delivery.driver_id is not None:
        driver = (
            db.query(User)
            .filter(
                User.id == delivery.driver_id
            )
            .first()
        )

    order = (
        db.query(Order)
        .filter(Order.id == delivery.order_id)
        .first()
    )

    return success_response(
        data=_build_delivery_response(
            delivery,
            customer=customer,
            driver=driver,
            order=order,
        ),
        message="Delivery retrieved successfully.",
    )


@router.patch("/{delivery_id}/assign-driver")
def assign_driver(
    delivery_id: int,
    payload: AssignDriverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    delivery = _get_delivery_or_404(
        db,
        delivery_id,
    )

    blocked_statuses = {
        DeliveryStatus.DELIVERED,
        DeliveryStatus.CANCELLED,
    }

    if delivery.status in blocked_statuses:
        raise BadRequestException(
            "A driver cannot be assigned to a "
            f"{_enum_value(delivery.status)} delivery."
        )

    driver = _get_active_driver_or_404(
        db,
        payload.driver_id,
    )

    delivery.driver_id = driver.id
    delivery.status = DeliveryStatus.ASSIGNED

    try:
        db.commit()
        db.refresh(delivery)

    except Exception:
        db.rollback()
        raise

    customer = (
        db.query(User)
        .filter(User.id == delivery.user_id)
        .first()
    )

    order = (
        db.query(Order)
        .filter(Order.id == delivery.order_id)
        .first()
    )

    return updated_response(
        data=_build_delivery_response(
            delivery,
            customer=customer,
            driver=driver,
            order=order,
        ),
        message="Driver assigned successfully.",
    )

@router.patch("/{delivery_id}/remove-driver")
def remove_driver(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    delivery = _get_delivery_or_404(
        db,
        delivery_id,
    )

    blocked_statuses = {
        DeliveryStatus.PICKED_UP,
        DeliveryStatus.OUT_FOR_DELIVERY,
        DeliveryStatus.DELIVERED,
        DeliveryStatus.CANCELLED,
    }

    if delivery.status in blocked_statuses:
        raise BadRequestException(
            "The driver cannot be removed after "
            "delivery processing has started."
        )

    if delivery.driver_id is None:
        raise BadRequestException(
            "This delivery does not have an "
            "assigned driver."
        )

    delivery.driver_id = None
    delivery.status = DeliveryStatus.PENDING

    try:
        db.commit()
        db.refresh(delivery)

    except Exception:
        db.rollback()
        raise

    customer = (
        db.query(User)
        .filter(User.id == delivery.user_id)
        .first()
    )

    order = (
        db.query(Order)
        .filter(Order.id == delivery.order_id)
        .first()
    )

    return updated_response(
        data=_build_delivery_response(
            delivery,
            customer=customer,
            driver=None,
            order=order,
        ),
        message="Driver removed successfully.",
    )

@router.patch("/{delivery_id}/cancel")
def cancel_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    delivery = _get_delivery_or_404(
        db,
        delivery_id,
    )

    if delivery.status == DeliveryStatus.DELIVERED:
        raise BadRequestException(
            "A delivered delivery cannot be "
            "cancelled."
        )

    if delivery.status == DeliveryStatus.CANCELLED:
        raise BadRequestException(
            "This delivery is already cancelled."
        )

    order = (
        db.query(Order)
        .filter(Order.id == delivery.order_id)
        .first()
    )

    delivery.status = DeliveryStatus.CANCELLED

    if order is not None:
        order.status = OrderStatus.CANCELLED

    try:
        db.commit()
        db.refresh(delivery)

    except Exception:
        db.rollback()
        raise

    customer = (
        db.query(User)
        .filter(User.id == delivery.user_id)
        .first()
    )

    driver = None

    if delivery.driver_id is not None:
        driver = (
            db.query(User)
            .filter(
                User.id == delivery.driver_id
            )
            .first()
        )

    return updated_response(
        data=_build_delivery_response(
            delivery,
            customer=customer,
            driver=driver,
            order=order,
        ),
        message="Delivery cancelled successfully.",
    )