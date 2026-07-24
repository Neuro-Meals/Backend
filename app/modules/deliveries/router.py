from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
from app.modules.deliveries import service
from app.modules.deliveries.models import (
    Delivery,
    DeliveryStatus,
)
from app.modules.deliveries.schemas import (
    FailDeliveryRequest,
    UpdateDriverLocation,
)
from app.modules.orders.models import Order
from app.modules.users.models import (
    User,
    UserRole,
)


router = APIRouter(
    prefix="/deliveries",
    tags=["Deliveries"],
)


# ============================================================
# Request schemas used only by delivery routes
# ============================================================


class CreateDeliveryRequest(BaseModel):
    """
    Creates the delivery tracking record for an existing order.

    Customer, driver, address, delivery date and delivery time
    are stored on the Order model. Delivery stores tracking state.
    """

    order_id: int = Field(..., ge=1)


class AssignDriverRequest(BaseModel):
    driver_id: int = Field(..., ge=1)


class DeliveryDateFilter(BaseModel):
    delivery_date: date | None = None


# ============================================================
# Role dependencies
# ============================================================


management_dependency = require_roles(
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.DELIVERY_MANAGER,
)

driver_dependency = require_roles(
    UserRole.DRIVER,
)

management_or_driver_dependency = require_roles(
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.DELIVERY_MANAGER,
    UserRole.DRIVER,
)


# ============================================================
# Small serialization helpers
# ============================================================


def _enum_value(value: Any) -> Any:
    if value is None:
        return None

    return value.value if hasattr(value, "value") else value


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None

    first_name = getattr(user, "first_name", None) or ""
    last_name = getattr(user, "last_name", None) or ""

    full_name = f"{first_name} {last_name}".strip()

    return full_name or None


def _serialize_customer(
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
        "email": getattr(
            customer,
            "email",
            None,
        ),
        "phone": getattr(
            customer,
            "phone",
            None,
        ),
    }


def _serialize_driver(
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
        "email": getattr(
            driver,
            "email",
            None,
        ),
        "phone": getattr(
            driver,
            "phone",
            None,
        ),
        "is_active": getattr(
            driver,
            "is_active",
            None,
        ),
    }


def _serialize_order(
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
            getattr(
                order,
                "status",
                None,
            )
        ),
        "user_id": getattr(
            order,
            "user_id",
            None,
        ),
        "driver_id": getattr(
            order,
            "driver_id",
            None,
        ),
        "meal_category_id": getattr(
            order,
            "meal_category_id",
            None,
        ),
        "delivery_date": getattr(
            order,
            "delivery_date",
            None,
        ),
        "delivery_time": getattr(
            order,
            "delivery_time",
            None,
        ),
        "delivery_address": getattr(
            order,
            "delivery_address",
            None,
        ),
        "delivery_notes": getattr(
            order,
            "delivery_notes",
            None,
        ),
        "total_amount": getattr(
            order,
            "total_amount",
            None,
        ),
        "items": getattr(
            order,
            "items",
            None,
        )
        or [],
    }


def _serialize_delivery(
    delivery: Delivery,
    *,
    order: Order | None = None,
    customer: User | None = None,
    driver: User | None = None,
) -> dict[str, Any]:
    """
    Serialize a delivery using the new architecture.

    Delivery:
        tracking state

    Order:
        customer, driver, address, date, time and items
    """

    if order is None:
        order = getattr(
            delivery,
            "order",
            None,
        )

    if customer is None and order is not None:
        customer = getattr(
            order,
            "user",
            None,
        )

        if customer is None:
            customer = getattr(
                order,
                "customer",
                None,
            )

    if driver is None and order is not None:
        driver = getattr(
            order,
            "driver",
            None,
        )

    return {
        "id": delivery.id,
        "order_id": delivery.order_id,
        "status": _enum_value(
            delivery.status
        ),
        "ready_for_pickup_at": getattr(
            delivery,
            "ready_for_pickup_at",
            None,
        ),
        "picked_up_at": getattr(
            delivery,
            "picked_up_at",
            None,
        ),
        "out_for_delivery_at": getattr(
            delivery,
            "out_for_delivery_at",
            None,
        ),
        "delivered_at": getattr(
            delivery,
            "delivered_at",
            None,
        ),
        "failed_at": getattr(
            delivery,
            "failed_at",
            None,
        ),
        "cancelled_at": getattr(
            delivery,
            "cancelled_at",
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
        "created_at": delivery.created_at,
        "updated_at": delivery.updated_at,
        "order": _serialize_order(order),
        "customer": _serialize_customer(
            customer
        ),
        "driver": _serialize_driver(driver),
    }


def _serialize_delivery_collection(
    deliveries: list[Delivery],
) -> list[dict[str, Any]]:
    return [
        _serialize_delivery(delivery)
        for delivery in deliveries
    ]


# ============================================================
# Management endpoints
# ============================================================


@router.post("/")
def create_delivery(
    payload: CreateDeliveryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_dependency
    ),
):
    """
    Create a delivery tracking record for an order.

    The order must already contain:

    - customer/user
    - driver
    - delivery address
    - delivery date
    - delivery time

    A second delivery cannot be created for the same order.
    """

    delivery = service.create_delivery(
        db=db,
        order_id=payload.order_id,
    )

    return created_response(
        data=_serialize_delivery(delivery),
        message="Delivery created successfully.",
    )


@router.get("/dashboard")
def delivery_dashboard(
    delivery_date: date | None = Query(
        default=None,
        description=(
            "Optional date used for dashboard statistics."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_dependency
    ),
):
    """
    Delivery management dashboard.

    Admin, super admin and delivery manager can access it.
    """

    statistics = service.get_delivery_statistics(
        db=db,
        delivery_date=delivery_date,
    )

    recent_deliveries = (
        service.get_recent_deliveries(
            db=db,
            limit=10,
        )
    )

    return dashboard_response(
        overview={
            "total_deliveries": (
                statistics.get(
                    "total_deliveries",
                    0,
                )
            ),
            "scheduled_today": (
                statistics.get(
                    "scheduled_today",
                    0,
                )
            ),
            "delivered_today": (
                statistics.get(
                    "delivered_today",
                    0,
                )
            ),
            "failed_today": (
                statistics.get(
                    "failed_today",
                    0,
                )
            ),
        },
        statistics={
            "by_status": statistics.get(
                "by_status",
                {},
            ),
        },
        charts={
            "daily_deliveries": statistics.get(
                "daily_deliveries",
                [],
            ),
        },
        recent_activity=(
            _serialize_delivery_collection(
                recent_deliveries
            )
        ),
    )


@router.get("/")
def list_deliveries(
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    delivery_status: DeliveryStatus | None = Query(
        default=None,
        alias="status",
    ),
    customer_id: int | None = Query(
        default=None,
        ge=1,
    ),
    driver_id: int | None = Query(
        default=None,
        ge=1,
    ),
    order_id: int | None = Query(
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
        management_dependency
    ),
):
    """
    Paginated delivery list for management users.

    Search is performed using data stored on Order, including:

    - order number
    - customer name
    - customer email
    - customer phone
    - delivery address
    """

    deliveries, total = service.list_deliveries(
        db=db,
        search=search,
        delivery_status=delivery_status,
        customer_id=customer_id,
        driver_id=driver_id,
        order_id=order_id,
        delivery_date=delivery_date,
        page=page,
        limit=limit,
    )

    return list_response(
        items=_serialize_delivery_collection(
            deliveries
        ),
        page=page,
        limit=limit,
        total=total,
        message="Deliveries retrieved successfully.",
    )


@router.get("/recent")
def recent_deliveries(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_dependency
    ),
):
    deliveries = service.get_recent_deliveries(
        db=db,
        limit=limit,
    )

    return success_response(
        data=_serialize_delivery_collection(
            deliveries
        ),
        message=(
            "Recent deliveries retrieved successfully."
        ),
    )


@router.get("/status/{delivery_status}")
def deliveries_by_status(
    delivery_status: DeliveryStatus,
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
        management_dependency
    ),
):
    deliveries, total = (
        service.list_deliveries(
            db=db,
            delivery_status=delivery_status,
            page=page,
            limit=limit,
        )
    )

    return list_response(
        items=_serialize_delivery_collection(
            deliveries
        ),
        page=page,
        limit=limit,
        total=total,
        message=(
            f"{_enum_value(delivery_status)} "
            "deliveries retrieved successfully."
        ),
    )


@router.get("/customer/{customer_id}/history")
def customer_delivery_history(
    customer_id: int = Path(
        ...,
        ge=1,
    ),
    delivery_status: DeliveryStatus | None = Query(
        default=None,
        alias="status",
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
        management_dependency
    ),
):
    deliveries, total = (
        service.get_customer_delivery_history(
            db=db,
            customer_id=customer_id,
            delivery_status=delivery_status,
            delivery_date=delivery_date,
            page=page,
            limit=limit,
        )
    )

    return list_response(
        items=_serialize_delivery_collection(
            deliveries
        ),
        page=page,
        limit=limit,
        total=total,
        message=(
            "Customer delivery history retrieved "
            "successfully."
        ),
    )


@router.get("/driver/{driver_id}/history")
def driver_delivery_history(
    driver_id: int = Path(
        ...,
        ge=1,
    ),
    delivery_status: DeliveryStatus | None = Query(
        default=None,
        alias="status",
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
        management_dependency
    ),
):
    deliveries, total = (
        service.get_driver_delivery_history(
            db=db,
            driver_id=driver_id,
            delivery_status=delivery_status,
            delivery_date=delivery_date,
            page=page,
            limit=limit,
        )
    )

    return list_response(
        items=_serialize_delivery_collection(
            deliveries
        ),
        page=page,
        limit=limit,
        total=total,
        message=(
            "Driver delivery history retrieved "
            "successfully."
        ),
    )


# ============================================================
# Current customer endpoints
# ============================================================


@router.get("/my")
def my_deliveries(
    delivery_status: DeliveryStatus | None = Query(
        default=None,
        alias="status",
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
        get_current_user
    ),
):
    """
    Return deliveries belonging to the currently logged-in
    customer.

    Access is checked through Order.user_id.
    """

    deliveries, total = (
        service.get_customer_delivery_history(
            db=db,
            customer_id=current_user.id,
            delivery_status=delivery_status,
            delivery_date=delivery_date,
            page=page,
            limit=limit,
        )
    )

    return list_response(
        items=_serialize_delivery_collection(
            deliveries
        ),
        page=page,
        limit=limit,
        total=total,
        message=(
            "Your deliveries were retrieved "
            "successfully."
        ),
    )


@router.get("/my/current")
def my_current_delivery(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    delivery = (
        service.get_customer_current_delivery(
            db=db,
            customer_id=current_user.id,
        )
    )

    return success_response(
        data=(
            _serialize_delivery(delivery)
            if delivery is not None
            else None
        ),
        message=(
            "Current delivery retrieved successfully."
            if delivery is not None
            else "You do not have an active delivery."
        ),
    )


@router.get("/order/{order_id}")
def get_delivery_by_order(
    order_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Return a delivery by order ID.

    Management users may access any delivery.

    Customers may access deliveries for their own orders.

    Drivers may access deliveries for orders assigned to them.
    """

    delivery = service.get_delivery_by_order_id(
        db=db,
        order_id=order_id,
    )

    service.ensure_delivery_access(
        delivery=delivery,
        current_user=current_user,
    )

    return success_response(
        data=_serialize_delivery(delivery),
        message="Delivery retrieved successfully.",
    )


# ============================================================
# Driver assignment endpoints
# ============================================================


@router.patch("/{delivery_id}/assign-driver")
def assign_driver(
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    payload: AssignDriverRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_dependency
    ),
):
    """
    Assign or replace the driver on the related Order.

    The driver ID is stored in Order.driver_id, not Delivery.
    """

    delivery = (
        service.assign_driver_to_delivery(
            db=db,
            delivery_id=delivery_id,
            driver_id=payload.driver_id,
        )
    )

    return updated_response(
        data=_serialize_delivery(delivery),
        message="Driver assigned successfully.",
    )


@router.patch(
    "/{delivery_id}/assign-dedicated-driver"
)
def assign_dedicated_driver(
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_dependency
    ),
):
    """
    Assign the customer's active dedicated driver.
    """

    delivery = (
        service.assign_customer_dedicated_driver(
            db=db,
            delivery_id=delivery_id,
        )
    )

    return updated_response(
        data=_serialize_delivery(delivery),
        message=(
            "Customer dedicated driver assigned "
            "successfully."
        ),
    )


@router.patch("/{delivery_id}/remove-driver")
def remove_driver(
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_dependency
    ),
):
    """
    Remove the assigned driver before delivery processing starts.

    This endpoint only works when Order.driver_id is nullable.

    When your business requires every delivery order to always
    contain a driver, the service will return a conflict response.
    """

    delivery = (
        service.remove_driver_from_delivery(
            db=db,
            delivery_id=delivery_id,
        )
    )

    return updated_response(
        data=_serialize_delivery(delivery),
        message="Driver removed successfully.",
    )


# ============================================================
# End of Response 1
# Response 2 continues with:
#
# - get one delivery
# - ready for pickup
# - pickup
# - out for delivery
# - delivered
# - failed
# - retry
# - cancel
# ============================================================

# ============================================================
# Additional route-only request schemas
# ============================================================


class CancelDeliveryRequest(BaseModel):
    reason: str | None = Field(
        default=None,
        max_length=500,
    )


# ============================================================
# Authorization helpers
# ============================================================


MANAGEMENT_ROLES = {
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.DELIVERY_MANAGER,
}


def _user_has_role(
    user: User,
    expected_roles: set[UserRole],
) -> bool:
    """
    Support projects where User.role may be stored either as
    a UserRole enum or as its string value.
    """

    current_role = getattr(user, "role", None)

    if current_role in expected_roles:
        return True

    current_role_value = _enum_value(current_role)

    return current_role_value in {
        _enum_value(role)
        for role in expected_roles
    }


def _ensure_management_user(
    current_user: User,
) -> None:
    if not _user_has_role(
        current_user,
        MANAGEMENT_ROLES,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only an admin, super admin, or delivery "
                "manager can perform this operation."
            ),
        )


def _ensure_assigned_driver(
    delivery: Delivery,
    current_user: User,
) -> None:
    """
    Ensure the logged-in user is the driver assigned through
    Delivery.order.driver_id.
    """

    if not _user_has_role(
        current_user,
        {UserRole.DRIVER},
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Driver access is required.",
        )

    service.ensure_driver_can_access_delivery(
        delivery=delivery,
        driver_id=current_user.id,
    )


def _ensure_management_or_assigned_driver(
    delivery: Delivery,
    current_user: User,
) -> None:
    """
    Management users can operate on any delivery.

    A driver can only operate on deliveries assigned to that
    driver through Order.driver_id.
    """

    if _user_has_role(
        current_user,
        MANAGEMENT_ROLES,
    ):
        return

    _ensure_assigned_driver(
        delivery=delivery,
        current_user=current_user,
    )


def _ensure_delivery_read_access(
    delivery: Delivery,
    current_user: User,
) -> None:
    """
    Allow access to:

    - management users
    - the customer who owns the order
    - the driver assigned to the order
    """

    if _user_has_role(
        current_user,
        MANAGEMENT_ROLES,
    ):
        return

    if _user_has_role(
        current_user,
        {UserRole.DRIVER},
    ):
        service.ensure_driver_can_access_delivery(
            delivery=delivery,
            driver_id=current_user.id,
        )
        return

    service.ensure_customer_can_access_delivery(
        delivery=delivery,
        customer_id=current_user.id,
    )


# ============================================================
# Driver dashboard endpoints
# ============================================================


@router.get("/driver/me/today")
def my_driver_deliveries_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        driver_dependency
    ),
):
    """
    Return all deliveries assigned to the logged-in driver
    for today's delivery date.
    """

    deliveries = (
        service.get_driver_today_deliveries(
            db=db,
            driver_id=current_user.id,
        )
    )

    return success_response(
        data=_serialize_delivery_collection(
            deliveries
        ),
        message=(
            "Today's driver deliveries retrieved "
            "successfully."
        ),
    )


@router.get("/driver/me/tomorrow")
def my_driver_deliveries_tomorrow(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        driver_dependency
    ),
):
    """
    Return all deliveries assigned to the logged-in driver
    for tomorrow's delivery date.
    """

    deliveries = (
        service.get_driver_tomorrow_deliveries(
            db=db,
            driver_id=current_user.id,
        )
    )

    return success_response(
        data=_serialize_delivery_collection(
            deliveries
        ),
        message=(
            "Tomorrow's driver deliveries retrieved "
            "successfully."
        ),
    )


@router.get("/driver/me/history")
def my_driver_delivery_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        driver_dependency
    ),
):
    """
    Return the logged-in driver's completed, failed, and
    cancelled delivery history.
    """

    deliveries = (
        service.get_driver_delivery_history(
            db=db,
            driver_id=current_user.id,
        )
    )

    return success_response(
        data=_serialize_delivery_collection(
            deliveries
        ),
        message=(
            "Driver delivery history retrieved "
            "successfully."
        ),
    )


@router.get("/driver/me/dashboard")
def my_driver_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        driver_dependency
    ),
):
    """
    Return a simple dashboard for the currently logged-in
    driver.
    """

    today_deliveries = (
        service.get_driver_today_deliveries(
            db=db,
            driver_id=current_user.id,
        )
    )

    tomorrow_deliveries = (
        service.get_driver_tomorrow_deliveries(
            db=db,
            driver_id=current_user.id,
        )
    )

    history = (
        service.get_driver_delivery_history(
            db=db,
            driver_id=current_user.id,
        )
    )

    active_statuses = {
        DeliveryStatus.PENDING,
        DeliveryStatus.READY_FOR_PICKUP,
        DeliveryStatus.PICKED_UP,
        DeliveryStatus.OUT_FOR_DELIVERY,
    }

    active_today = [
        delivery
        for delivery in today_deliveries
        if delivery.status in active_statuses
    ]

    delivered_today = [
        delivery
        for delivery in today_deliveries
        if delivery.status
        == DeliveryStatus.DELIVERED
    ]

    failed_today = [
        delivery
        for delivery in today_deliveries
        if delivery.status
        == DeliveryStatus.FAILED
    ]

    return dashboard_response(
        overview={
            "driver_id": current_user.id,
            "driver_name": _full_name(
                current_user
            ),
            "today_total": len(
                today_deliveries
            ),
            "today_active": len(
                active_today
            ),
            "today_delivered": len(
                delivered_today
            ),
            "today_failed": len(
                failed_today
            ),
            "tomorrow_total": len(
                tomorrow_deliveries
            ),
            "history_total": len(history),
        },
        statistics={
            "pending": sum(
                1
                for delivery in today_deliveries
                if delivery.status
                == DeliveryStatus.PENDING
            ),
            "ready_for_pickup": sum(
                1
                for delivery in today_deliveries
                if delivery.status
                == DeliveryStatus.READY_FOR_PICKUP
            ),
            "picked_up": sum(
                1
                for delivery in today_deliveries
                if delivery.status
                == DeliveryStatus.PICKED_UP
            ),
            "out_for_delivery": sum(
                1
                for delivery in today_deliveries
                if delivery.status
                == DeliveryStatus.OUT_FOR_DELIVERY
            ),
            "delivered": len(
                delivered_today
            ),
            "failed": len(
                failed_today
            ),
        },
        charts={},
        recent_activity=(
            _serialize_delivery_collection(
                today_deliveries[:10]
            )
        ),
    )


# ============================================================
# Delivery status transition endpoints
# ============================================================


@router.patch(
    "/{delivery_id}/ready-for-pickup"
)
def mark_ready_for_pickup(
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_dependency
    ),
):
    """
    Mark a pending or failed delivery as ready for pickup.

    This operation is intended for management after the kitchen
    or chef confirms that the order is ready.
    """

    delivery = (
        service.mark_delivery_ready_for_pickup(
            db=db,
            delivery_id=delivery_id,
        )
    )

    return updated_response(
        data=_serialize_delivery(delivery),
        message=(
            "Delivery marked as ready for pickup."
        ),
    )


@router.patch("/{delivery_id}/pick-up")
def mark_picked_up(
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_or_driver_dependency
    ),
):
    """
    Mark food as collected by the assigned driver.
    """

    existing_delivery = (
        service.get_delivery_or_404(
            db=db,
            delivery_id=delivery_id,
        )
    )

    _ensure_management_or_assigned_driver(
        delivery=existing_delivery,
        current_user=current_user,
    )

    delivery = (
        service.mark_delivery_picked_up(
            db=db,
            delivery_id=delivery_id,
        )
    )

    return updated_response(
        data=_serialize_delivery(delivery),
        message=(
            "Delivery marked as picked up."
        ),
    )


@router.patch(
    "/{delivery_id}/out-for-delivery"
)
def mark_out_for_delivery(
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_or_driver_dependency
    ),
):
    """
    Mark a picked-up delivery as out for delivery.

    The service also updates the connected Order status.
    """

    existing_delivery = (
        service.get_delivery_or_404(
            db=db,
            delivery_id=delivery_id,
        )
    )

    _ensure_management_or_assigned_driver(
        delivery=existing_delivery,
        current_user=current_user,
    )

    delivery = (
        service.mark_delivery_out_for_delivery(
            db=db,
            delivery_id=delivery_id,
        )
    )

    return updated_response(
        data=_serialize_delivery(delivery),
        message=(
            "Delivery is now out for delivery."
        ),
    )


@router.patch("/{delivery_id}/delivered")
def mark_delivered(
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_or_driver_dependency
    ),
):
    """
    Complete the delivery.

    The service updates both Delivery and Order to delivered.
    """

    existing_delivery = (
        service.get_delivery_or_404(
            db=db,
            delivery_id=delivery_id,
        )
    )

    _ensure_management_or_assigned_driver(
        delivery=existing_delivery,
        current_user=current_user,
    )

    delivery = (
        service.mark_delivery_delivered(
            db=db,
            delivery_id=delivery_id,
        )
    )

    return updated_response(
        data=_serialize_delivery(delivery),
        message=(
            "Delivery completed successfully."
        ),
    )


@router.patch("/{delivery_id}/failed")
def mark_failed(
    payload: FailDeliveryRequest,
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_or_driver_dependency
    ),
):
    """
    Mark an active delivery attempt as failed.

    The related Order returns to READY_FOR_DELIVERY so the
    operation may be retried.
    """

    existing_delivery = (
        service.get_delivery_or_404(
            db=db,
            delivery_id=delivery_id,
        )
    )

    _ensure_management_or_assigned_driver(
        delivery=existing_delivery,
        current_user=current_user,
    )

    delivery = (
        service.mark_delivery_failed(
            db=db,
            delivery_id=delivery_id,
            reason=payload.reason,
        )
    )

    return updated_response(
        data=_serialize_delivery(delivery),
        message=(
            "Delivery marked as failed."
        ),
    )


@router.patch("/{delivery_id}/retry")
def retry_delivery(
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_dependency
    ),
):
    """
    Return a failed delivery to READY_FOR_PICKUP.
    """

    delivery = (
        service.retry_failed_delivery(
            db=db,
            delivery_id=delivery_id,
        )
    )

    return updated_response(
        data=_serialize_delivery(delivery),
        message=(
            "Failed delivery is ready for another attempt."
        ),
    )


@router.patch("/{delivery_id}/cancel")
def cancel_delivery(
    payload: CancelDeliveryRequest,
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_dependency
    ),
):
    """
    Cancel a delivery before it reaches out-for-delivery or
    delivered status.

    The connected Order is also cancelled by the service.
    """

    delivery = service.cancel_delivery(
        db=db,
        delivery_id=delivery_id,
        reason=payload.reason,
    )

    return updated_response(
        data=_serialize_delivery(delivery),
        message=(
            "Delivery cancelled successfully."
        ),
    )


# ============================================================
# Driver GPS location endpoint
# ============================================================


@router.patch("/{delivery_id}/location")
def update_delivery_location(
    payload: UpdateDriverLocation,
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        management_or_driver_dependency
    ),
):
    """
    Update the current driver GPS position.

    A driver can update only a delivery assigned to them.
    Management users can update any active delivery.
    """

    existing_delivery = (
        service.get_delivery_or_404(
            db=db,
            delivery_id=delivery_id,
        )
    )

    _ensure_management_or_assigned_driver(
        delivery=existing_delivery,
        current_user=current_user,
    )

    delivery = service.update_driver_location(
        db=db,
        delivery_id=delivery_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )

    return updated_response(
        data=_serialize_delivery(delivery),
        message=(
            "Driver location updated successfully."
        ),
    )


# ============================================================
# Public/customer tracking endpoint
# ============================================================


@router.get(
    "/{delivery_id}/tracking"
)
def track_delivery(
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Return delivery tracking information.

    Customers may track their own order.

    Assigned drivers and management users may also access it.
    """

    delivery = service.get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    _ensure_delivery_read_access(
        delivery=delivery,
        current_user=current_user,
    )

    order = service.get_order_for_delivery(
        db=db,
        delivery=delivery,
    )

    return success_response(
        data={
            "delivery_id": delivery.id,
            "order_id": delivery.order_id,
            "order_number": getattr(
                order,
                "order_number",
                None,
            ),
            "status": _enum_value(
                delivery.status
            ),
            "delivery_date": getattr(
                order,
                "delivery_date",
                None,
            ),
            "delivery_time": getattr(
                order,
                "delivery_time",
                None,
            ),
            "delivery_address": getattr(
                order,
                "delivery_address",
                None,
            ),
            "driver": _serialize_driver(
                getattr(
                    order,
                    "driver",
                    None,
                )
            ),
            "current_location": {
                "latitude": getattr(
                    delivery,
                    "current_latitude",
                    None,
                ),
                "longitude": getattr(
                    delivery,
                    "current_longitude",
                    None,
                ),
            },
            "timeline": {
                "ready_for_pickup_at": getattr(
                    delivery,
                    "ready_for_pickup_at",
                    None,
                ),
                "picked_up_at": getattr(
                    delivery,
                    "picked_up_at",
                    None,
                ),
                "out_for_delivery_at": getattr(
                    delivery,
                    "out_for_delivery_at",
                    None,
                ),
                "delivered_at": getattr(
                    delivery,
                    "delivered_at",
                    None,
                ),
                "failed_at": getattr(
                    delivery,
                    "failed_at",
                    None,
                ),
                "cancelled_at": getattr(
                    delivery,
                    "cancelled_at",
                    None,
                ),
            },
            "failure_reason": getattr(
                delivery,
                "failure_reason",
                None,
            ),
        },
        message=(
            "Delivery tracking retrieved successfully."
        ),
    )


# ============================================================
# Single-delivery endpoint
#
# Keep this endpoint below all fixed paths such as:
#
# /dashboard
# /recent
# /my
# /driver/me/today
# /order/{order_id}
#
# This prevents FastAPI from treating those path names as a
# delivery ID.
# ============================================================


@router.get("/{delivery_id}")
def get_delivery(
    delivery_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    delivery = service.get_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
    )

    _ensure_delivery_read_access(
        delivery=delivery,
        current_user=current_user,
    )

    return success_response(
        data=_serialize_delivery(delivery),
        message="Delivery retrieved successfully.",
    )


# ============================================================
# End of Response 2
#
# Response 3 will provide:
#
# 1. Required corrections for Response 1 service calls.
# 2. Missing service compatibility functions.
# 3. Correct statistics integration.
# 4. Router registration in main.py.
# 5. Model relationship checks.
# 6. Import and endpoint testing commands.
# ============================================================