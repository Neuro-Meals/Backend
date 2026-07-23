from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.deliveries.models import Delivery, DeliveryStatus
from app.modules.deliveries.schemas import (
    DeliveryResponse,
    DriverDeliveryResponse,
    UpdateDriverLocation,
)
from app.modules.notifications.models import (
    Notification,
    NotificationChannel,
    NotificationType,
)
from app.modules.orders.models import Order, OrderStatus
from app.modules.users.models import User, UserRole


router = APIRouter(
    prefix="/driver",
    tags=["Driver App"],
)

class DriverCreate(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=30)
    password: str = Field(..., min_length=6, max_length=128)

    location: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)


class DriverUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=2, max_length=100)
    last_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, min_length=7, max_length=30)

    location: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)

    is_active: bool | None = None


class FailDeliveryRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)

def enum_value(value):
    if value is None:
        return None

    return value.value if hasattr(value, "value") else value


def beginning_of_day(value: date | None = None) -> datetime:
    target_date = value or datetime.utcnow().date()
    return datetime.combine(target_date, time.min)


def end_of_day(value: date | None = None) -> datetime:
    return beginning_of_day(value) + timedelta(days=1)


def serialize_driver(driver: User) -> dict:
    return {
        "id": driver.id,
        "first_name": driver.first_name,
        "last_name": driver.last_name,
        "full_name": (
            f"{driver.first_name or ''} {driver.last_name or ''}".strip()
        ),
        "email": driver.email,
        "phone": driver.phone,
        "location": driver.location,
        "address": driver.address,
        "role": enum_value(driver.role),
        "is_active": driver.is_active,
        "is_verified": driver.is_verified,
        "created_at": driver.created_at,
        "updated_at": getattr(driver, "updated_at", None),
    }


def get_driver_or_404(
    db: Session,
    driver_id: int,
) -> User:
    driver = (
        db.query(User)
        .filter(
            User.id == driver_id,
            User.role == UserRole.DRIVER,
        )
        .first()
    )

    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found",
        )

    return driver


def get_driver_delivery_or_404(
    db: Session,
    delivery_id: int,
    driver_id: int,
) -> Delivery:
    delivery = (
        db.query(Delivery)
        .filter(
            Delivery.id == delivery_id,
            Delivery.driver_id == driver_id,
        )
        .first()
    )

    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery not found or not assigned to this driver",
        )

    return delivery


def get_delivery_order(
    db: Session,
    delivery: Delivery,
) -> Order | None:
    return (
        db.query(Order)
        .filter(Order.id == delivery.order_id)
        .first()
    )


def ensure_driver_is_active(current_user: User) -> None:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Driver account is inactive",
        )


def ensure_delivery_not_finished(delivery: Delivery) -> None:
    finished_statuses = {
        DeliveryStatus.DELIVERED,
        DeliveryStatus.CANCELLED,
    }

    if delivery.status in finished_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Delivery is already {enum_value(delivery.status)} "
                "and cannot be changed"
            ),
        )


def build_driver_delivery_response(
    db: Session,
    delivery: Delivery,
) -> dict:
    customer = (
        db.query(User)
        .filter(User.id == delivery.user_id)
        .first()
    )

    driver = None

    if delivery.driver_id is not None:
        driver = (
            db.query(User)
            .filter(User.id == delivery.driver_id)
            .first()
        )

    order = (
        db.query(Order)
        .filter(Order.id == delivery.order_id)
        .first()
    )

    customer_full_name = None
    if customer:
        customer_full_name = (
            f"{customer.first_name or ''} "
            f"{customer.last_name or ''}"
        ).strip()

    driver_full_name = None
    if driver:
        driver_full_name = (
            f"{driver.first_name or ''} "
            f"{driver.last_name or ''}"
        ).strip()

    return {
        "id": delivery.id,
        "status": enum_value(delivery.status),
        "delivery_address": delivery.delivery_address,
        "delivery_notes": delivery.delivery_notes,
        "scheduled_at": delivery.scheduled_at,
        "picked_up_at": delivery.picked_up_at,
        "delivered_at": delivery.delivered_at,
        "current_latitude": delivery.current_latitude,
        "current_longitude": delivery.current_longitude,
        "failure_reason": delivery.failure_reason,
        "created_at": delivery.created_at,
        "updated_at": delivery.updated_at,
        "customer": (
            {
                "id": customer.id,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "full_name": customer_full_name,
                "email": customer.email,
                "phone": customer.phone,
                "location": customer.location,
                "address": customer.address,
            }
            if customer
            else None
        ),
        "driver": (
            {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "full_name": driver_full_name,
                "email": driver.email,
                "phone": driver.phone,
            }
            if driver
            else None
        ),
        "order": (
            {
                "id": order.id,
                "order_number": order.order_number,
                "status": enum_value(order.status),
                "total_amount": order.total_amount,
                "delivery_date": order.delivery_date,
                "items": order.items,
            }
            if order
            else None
        ),
    }


def create_driver_notification(
    db: Session,
    driver_id: int,
    title: str,
    message: str,
) -> None:
    notification = Notification(
        user_id=driver_id,
        title=title,
        message=message,
        notification_type=NotificationType.GENERAL.value,
        channel=NotificationChannel.IN_APP.value,
        is_read=False,
    )

    db.add(notification)

@router.post(
    "/admin",
    status_code=status.HTTP_201_CREATED,
)
def create_driver(
    payload: DriverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    normalized_email = payload.email.lower().strip()
    normalized_phone = payload.phone.strip()

    existing_email = (
        db.query(User)
        .filter(func.lower(User.email) == normalized_email)
        .first()
    )

    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    existing_phone = (
        db.query(User)
        .filter(User.phone == normalized_phone)
        .first()
    )

    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone already exists",
        )

    driver = User(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=normalized_email,
        phone=normalized_phone,
        location=payload.location,
        address=payload.address,
        hashed_password=hash_password(payload.password),
        role=UserRole.DRIVER,
        is_active=True,
        is_verified=True,
    )

    db.add(driver)
    db.flush()

    create_driver_notification(
        db=db,
        driver_id=driver.id,
        title="Welcome to the Nitro Delivery Team",
        message=(
            f"Hi {driver.first_name}, your driver account has been created. "
            f"Your login email is {driver.email}. "
            "Please change your password after your first login."
        ),
    )

    db.commit()
    db.refresh(driver)

    return serialize_driver(driver)


@router.get("/admin")
def list_drivers(
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    query = db.query(User).filter(
        User.role == UserRole.DRIVER
    )

    if search:
        search_value = f"%{search.strip()}%"

        query = query.filter(
            (
                User.first_name.ilike(search_value)
                | User.last_name.ilike(search_value)
                | User.email.ilike(search_value)
                | User.phone.ilike(search_value)
            )
        )

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    total = query.count()

    drivers = (
        query.order_by(User.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": [
            serialize_driver(driver)
            for driver in drivers
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


@router.get("/admin/{driver_id}")
def get_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    driver = get_driver_or_404(
        db=db,
        driver_id=driver_id,
    )

    total_deliveries = (
        db.query(Delivery)
        .filter(Delivery.driver_id == driver.id)
        .count()
    )

    completed_deliveries = (
        db.query(Delivery)
        .filter(
            Delivery.driver_id == driver.id,
            Delivery.status == DeliveryStatus.DELIVERED,
        )
        .count()
    )

    failed_deliveries = (
        db.query(Delivery)
        .filter(
            Delivery.driver_id == driver.id,
            Delivery.status == DeliveryStatus.FAILED,
        )
        .count()
    )

    active_deliveries = (
        db.query(Delivery)
        .filter(
            Delivery.driver_id == driver.id,
            Delivery.status.in_(
                [
                    DeliveryStatus.PENDING,
                    DeliveryStatus.ASSIGNED,
                    DeliveryStatus.PICKED_UP,
                    DeliveryStatus.OUT_FOR_DELIVERY,
                ]
            ),
        )
        .count()
    )

    return {
        **serialize_driver(driver),
        "delivery_statistics": {
            "total": total_deliveries,
            "active": active_deliveries,
            "completed": completed_deliveries,
            "failed": failed_deliveries,
        },
    }


@router.put("/admin/{driver_id}")
def update_driver(
    driver_id: int,
    payload: DriverUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    driver = get_driver_or_404(
        db=db,
        driver_id=driver_id,
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    if "phone" in update_data:
        phone = update_data["phone"].strip()

        existing_phone = (
            db.query(User)
            .filter(
                User.phone == phone,
                User.id != driver.id,
            )
            .first()
        )

        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone already exists",
            )

        update_data["phone"] = phone

    for field, value in update_data.items():
        setattr(driver, field, value)

    db.commit()
    db.refresh(driver)

    return serialize_driver(driver)


@router.patch("/admin/{driver_id}/activate")
def activate_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    driver = get_driver_or_404(
        db=db,
        driver_id=driver_id,
    )

    driver.is_active = True

    create_driver_notification(
        db=db,
        driver_id=driver.id,
        title="Driver Account Activated",
        message=(
            "Your driver account has been activated. "
            "You can now receive delivery assignments."
        ),
    )

    db.commit()
    db.refresh(driver)

    return {
        "message": "Driver activated successfully",
        "driver": serialize_driver(driver),
    }


@router.patch("/admin/{driver_id}/deactivate")
def deactivate_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    driver = get_driver_or_404(
        db=db,
        driver_id=driver_id,
    )

    active_delivery = (
        db.query(Delivery)
        .filter(
            Delivery.driver_id == driver.id,
            Delivery.status.in_(
                [
                    DeliveryStatus.PICKED_UP,
                    DeliveryStatus.OUT_FOR_DELIVERY,
                ]
            ),
        )
        .first()
    )

    if active_delivery:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Driver cannot be deactivated while carrying "
                "an active delivery"
            ),
        )

    driver.is_active = False

    create_driver_notification(
        db=db,
        driver_id=driver.id,
        title="Driver Account Deactivated",
        message=(
            "Your driver account has been deactivated. "
            "Contact an administrator for assistance."
        ),
    )

    db.commit()
    db.refresh(driver)

    return {
        "message": "Driver deactivated successfully",
        "driver": serialize_driver(driver),
    }


@router.delete("/admin/{driver_id}")
def delete_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    driver = get_driver_or_404(
        db=db,
        driver_id=driver_id,
    )

    active_delivery = (
        db.query(Delivery)
        .filter(
            Delivery.driver_id == driver.id,
            Delivery.status.in_(
                [
                    DeliveryStatus.PICKED_UP,
                    DeliveryStatus.OUT_FOR_DELIVERY,
                ]
            ),
        )
        .first()
    )

    if active_delivery:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Driver cannot be deleted while carrying "
                "an active delivery"
            ),
        )

    db.query(Delivery).filter(
        Delivery.driver_id == driver.id
    ).update(
        {
            "driver_id": None,
            "status": DeliveryStatus.PENDING,
        },
        synchronize_session=False,
    )

    db.query(Notification).filter(
        Notification.user_id == driver.id
    ).delete(
        synchronize_session=False
    )

    db.delete(driver)
    db.commit()

    return {
        "message": "Driver deleted successfully",
        "id": driver_id,
    }

@router.get("/me")
def get_driver_profile(
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    ensure_driver_is_active(current_user)

    return serialize_driver(current_user)

@router.get("/dashboard")
def driver_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    ensure_driver_is_active(current_user)

    today_start = beginning_of_day()
    tomorrow_start = end_of_day()

    base_query = db.query(Delivery).filter(
        Delivery.driver_id == current_user.id
    )

    total_assigned = base_query.count()

    pending_pickups = base_query.filter(
        Delivery.status.in_(
            [
                DeliveryStatus.PENDING,
                DeliveryStatus.ASSIGNED,
            ]
        )
    ).count()

    picked_up = base_query.filter(
        Delivery.status == DeliveryStatus.PICKED_UP
    ).count()

    out_for_delivery_count = base_query.filter(
        Delivery.status == DeliveryStatus.OUT_FOR_DELIVERY
    ).count()

    completed_today = base_query.filter(
        Delivery.status == DeliveryStatus.DELIVERED,
        Delivery.delivered_at >= today_start,
        Delivery.delivered_at < tomorrow_start,
    ).count()

    failed_today = base_query.filter(
        Delivery.status == DeliveryStatus.FAILED,
        Delivery.updated_at >= today_start,
        Delivery.updated_at < tomorrow_start,
    ).count()

    today_deliveries = base_query.filter(
        Delivery.scheduled_at >= today_start,
        Delivery.scheduled_at < tomorrow_start,
    ).count()

    current_delivery = (
        base_query.filter(
            Delivery.status.in_(
                [
                    DeliveryStatus.PICKED_UP,
                    DeliveryStatus.OUT_FOR_DELIVERY,
                ]
            )
        )
        .order_by(Delivery.id.asc())
        .first()
    )

    next_delivery = (
        base_query.filter(
            Delivery.status.in_(
                [
                    DeliveryStatus.PENDING,
                    DeliveryStatus.ASSIGNED,
                ]
            )
        )
        .order_by(
            Delivery.scheduled_at.asc(),
            Delivery.id.asc(),
        )
        .first()
    )

    return {
        "driver": serialize_driver(current_user),
        "summary": {
            "total_assigned": total_assigned,
            "today": today_deliveries,
            "pending_pickups": pending_pickups,
            "picked_up": picked_up,
            "out_for_delivery": out_for_delivery_count,
            "completed_today": completed_today,
            "failed_today": failed_today,
        },
        "current_delivery": (
            build_driver_delivery_response(
                db,
                current_delivery,
            )
            if current_delivery
            else None
        ),
        "next_delivery": (
            build_driver_delivery_response(
                db,
                next_delivery,
            )
            if next_delivery
            else None
        ),
    }

@router.get(
    "/deliveries",
    response_model=list[DriverDeliveryResponse],
)
def my_driver_deliveries(
    delivery_status: DeliveryStatus | None = Query(
        default=None,
        alias="status",
    ),
    scheduled_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    ensure_driver_is_active(current_user)

    query = db.query(Delivery).filter(
        Delivery.driver_id == current_user.id
    )

    if delivery_status:
        query = query.filter(
            Delivery.status == delivery_status
        )

    if scheduled_date:
        start = beginning_of_day(scheduled_date)
        finish = end_of_day(scheduled_date)

        query = query.filter(
            Delivery.scheduled_at >= start,
            Delivery.scheduled_at < finish,
        )

    deliveries = (
        query.order_by(
            Delivery.scheduled_at.asc(),
            Delivery.id.desc(),
        )
        .all()
    )

    return [
        build_driver_delivery_response(
            db,
            delivery,
        )
        for delivery in deliveries
    ]


@router.get(
    "/deliveries/today",
    response_model=list[DriverDeliveryResponse],
)
def today_driver_deliveries(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    ensure_driver_is_active(current_user)

    today_start = beginning_of_day()
    tomorrow_start = end_of_day()

    deliveries = (
        db.query(Delivery)
        .filter(
            Delivery.driver_id == current_user.id,
            Delivery.scheduled_at >= today_start,
            Delivery.scheduled_at < tomorrow_start,
        )
        .order_by(
            Delivery.scheduled_at.asc(),
            Delivery.id.asc(),
        )
        .all()
    )

    return [
        build_driver_delivery_response(
            db,
            delivery,
        )
        for delivery in deliveries
    ]


@router.get(
    "/deliveries/history",
    response_model=list[DriverDeliveryResponse],
)
def driver_delivery_history(
    delivery_status: DeliveryStatus | None = Query(
        default=None,
        alias="status",
    ),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    ensure_driver_is_active(current_user)

    query = db.query(Delivery).filter(
        Delivery.driver_id == current_user.id,
        Delivery.status.in_(
            [
                DeliveryStatus.DELIVERED,
                DeliveryStatus.FAILED,
                DeliveryStatus.CANCELLED,
            ]
        ),
    )

    if delivery_status:
        if delivery_status not in {
            DeliveryStatus.DELIVERED,
            DeliveryStatus.FAILED,
            DeliveryStatus.CANCELLED,
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "History only supports delivered, "
                    "failed, or cancelled statuses"
                ),
            )

        query = query.filter(
            Delivery.status == delivery_status
        )

    if start_date:
        query = query.filter(
            Delivery.updated_at >= beginning_of_day(
                start_date
            )
        )

    if end_date:
        query = query.filter(
            Delivery.updated_at < end_of_day(
                end_date
            )
        )

    deliveries = (
        query.order_by(Delivery.updated_at.desc())
        .limit(limit)
        .all()
    )

    return [
        build_driver_delivery_response(
            db,
            delivery,
        )
        for delivery in deliveries
    ]


@router.get(
    "/deliveries/{delivery_id}",
    response_model=DriverDeliveryResponse,
)
def get_my_driver_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    ensure_driver_is_active(current_user)

    delivery = get_driver_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
        driver_id=current_user.id,
    )

    return build_driver_delivery_response(
        db,
        delivery,
    )

@router.post(
    "/deliveries/{delivery_id}/pickup",
    response_model=DeliveryResponse,
)
def pickup_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    ensure_driver_is_active(current_user)

    delivery = get_driver_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
        driver_id=current_user.id,
    )

    if delivery.status not in {
        DeliveryStatus.PENDING,
        DeliveryStatus.ASSIGNED,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only pending or assigned deliveries "
                "can be picked up"
            ),
        )

    delivery.status = DeliveryStatus.PICKED_UP
    delivery.picked_up_at = datetime.utcnow()
    delivery.failure_reason = None

    order = get_delivery_order(
        db=db,
        delivery=delivery,
    )

    # Pickup and out-for-delivery are different steps.
    # Do not change the order to OUT_FOR_DELIVERY here.

    db.commit()
    db.refresh(delivery)

    return delivery


@router.post(
    "/deliveries/{delivery_id}/out-for-delivery",
    response_model=DeliveryResponse,
)
def out_for_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    ensure_driver_is_active(current_user)

    delivery = get_driver_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
        driver_id=current_user.id,
    )

    if delivery.status != DeliveryStatus.PICKED_UP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Delivery must be picked up before "
                "starting delivery"
            ),
        )

    delivery.status = DeliveryStatus.OUT_FOR_DELIVERY
    delivery.failure_reason = None

    order = get_delivery_order(
        db=db,
        delivery=delivery,
    )

    if order:
        order.status = OrderStatus.OUT_FOR_DELIVERY

    db.commit()
    db.refresh(delivery)

    return delivery


@router.post(
    "/deliveries/{delivery_id}/complete",
    response_model=DeliveryResponse,
)
def complete_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    ensure_driver_is_active(current_user)

    delivery = get_driver_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
        driver_id=current_user.id,
    )

    if delivery.status != DeliveryStatus.OUT_FOR_DELIVERY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Delivery must be out for delivery "
                "before it can be completed"
            ),
        )

    delivery.status = DeliveryStatus.DELIVERED
    delivery.delivered_at = datetime.utcnow()
    delivery.failure_reason = None

    order = get_delivery_order(
        db=db,
        delivery=delivery,
    )

    if order:
        order.status = OrderStatus.DELIVERED

    create_driver_notification(
        db=db,
        driver_id=current_user.id,
        title="Delivery Completed",
        message=(
            f"Delivery #{delivery.id} was completed successfully."
        ),
    )

    db.commit()
    db.refresh(delivery)

    return delivery


@router.post(
    "/deliveries/{delivery_id}/fail",
    response_model=DeliveryResponse,
)
def fail_delivery(
    delivery_id: int,
    payload: FailDeliveryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    ensure_driver_is_active(current_user)

    delivery = get_driver_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
        driver_id=current_user.id,
    )

    ensure_delivery_not_finished(delivery)

    if delivery.status not in {
        DeliveryStatus.ASSIGNED,
        DeliveryStatus.PICKED_UP,
        DeliveryStatus.OUT_FOR_DELIVERY,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This delivery cannot be marked as failed "
                "from its current status"
            ),
        )

    delivery.status = DeliveryStatus.FAILED
    delivery.failure_reason = payload.reason.strip()

    create_driver_notification(
        db=db,
        driver_id=current_user.id,
        title="Delivery Marked as Failed",
        message=(
            f"Delivery #{delivery.id} was marked as failed. "
            f"Reason: {delivery.failure_reason}"
        ),
    )

    db.commit()
    db.refresh(delivery)

    return delivery


@router.patch(
    "/deliveries/{delivery_id}/location",
    response_model=DeliveryResponse,
)
def update_delivery_location(
    delivery_id: int,
    payload: UpdateDriverLocation,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    ensure_driver_is_active(current_user)

    delivery = get_driver_delivery_or_404(
        db=db,
        delivery_id=delivery_id,
        driver_id=current_user.id,
    )

    ensure_delivery_not_finished(delivery)

    if delivery.status not in {
        DeliveryStatus.PICKED_UP,
        DeliveryStatus.OUT_FOR_DELIVERY,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Location can only be updated after pickup "
                "and before delivery completion"
            ),
        )

    if not -90 <= payload.latitude <= 90:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Latitude must be between -90 and 90",
        )

    if not -180 <= payload.longitude <= 180:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Longitude must be between -180 and 180",
        )

    delivery.current_latitude = payload.latitude
    delivery.current_longitude = payload.longitude

    db.commit()
    db.refresh(delivery)

    return delivery