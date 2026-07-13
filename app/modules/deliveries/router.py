from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.deliveries.models import Delivery, DeliveryStatus
from app.modules.deliveries.schemas import (
    AssignDriverRequest,
    DeliveryCreate,
    DeliveryResponse,
    DriverDeliveryResponse,
    UpdateDeliveryStatus,
    UpdateDriverLocation,
)
from app.modules.orders.models import Order, OrderStatus
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/deliveries", tags=["Deliveries"])

def enum_value(value):
    if value is None:
        return None

    return value.value if hasattr(value, "value") else value


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

    if delivery.driver_id:
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

        "customer": {
            "id": customer.id,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "full_name": (
                f"{customer.first_name} {customer.last_name}"
            ),
            "email": customer.email,
            "phone": customer.phone,
            "location": customer.location,
            "address": customer.address,
        }
        if customer
        else None,

        "driver": {
            "id": driver.id,
            "first_name": driver.first_name,
            "last_name": driver.last_name,
            "full_name": (
                f"{driver.first_name} {driver.last_name}"
            ),
            "email": driver.email,
            "phone": driver.phone,
        }
        if driver
        else None,

        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "status": enum_value(order.status),
            "total_amount": order.total_amount,
            "delivery_date": order.delivery_date,
            "items": order.items,
        }
        if order
        else None,
    }

@router.post("/", response_model=DeliveryResponse)
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
    order = db.query(Order).filter(Order.id == payload.order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    existing = db.query(Delivery).filter(Delivery.order_id == order.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Delivery already exists for this order")

    delivery = Delivery(
        order_id=order.id,
        user_id=order.user_id,
        driver_id=payload.driver_id,
        status=DeliveryStatus.ASSIGNED if payload.driver_id else DeliveryStatus.PENDING,
        delivery_address=payload.delivery_address or order.delivery_address,
        delivery_notes=payload.delivery_notes or order.delivery_notes,
        scheduled_at=payload.scheduled_at,
    )

    db.add(delivery)

    order.status = OrderStatus.READY_FOR_DELIVERY

    db.commit()
    db.refresh(delivery)

    return delivery


@router.get("/")
def list_deliveries(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
    search: str | None = Query(None),
    status: DeliveryStatus | None = Query(None),
    driver_id: int | None = Query(None),
    user_id: int | None = Query(None),
    order_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Delivery)

    if search:
        value = f"%{search}%"
        query = query.filter(
            or_(
                Delivery.delivery_address.ilike(value),
                Delivery.delivery_notes.ilike(value),
                Delivery.failure_reason.ilike(value),
            )
        )

    if status:
        query = query.filter(Delivery.status == status)

    if driver_id:
        query = query.filter(Delivery.driver_id == driver_id)

    if user_id:
        query = query.filter(Delivery.user_id == user_id)

    if order_id:
        query = query.filter(Delivery.order_id == order_id)

    total = query.count()

    deliveries = (
        query.order_by(Delivery.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": deliveries,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/my", response_model=list[DeliveryResponse])
def my_deliveries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Delivery)
        .filter(Delivery.user_id == current_user.id)
        .order_by(Delivery.id.desc())
        .all()
    )


@router.get(
    "/driver/my",
    response_model=list[DriverDeliveryResponse],
)
def driver_my_deliveries(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.DRIVER)
    ),
):
    deliveries = (
        db.query(Delivery)
        .filter(Delivery.driver_id == current_user.id)
        .order_by(Delivery.id.desc())
        .all()
    )

    return [
        build_driver_delivery_response(db, delivery)
        for delivery in deliveries
    ]


@router.get("/{delivery_id}", response_model=DeliveryResponse)
def get_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    if current_user.role == UserRole.CUSTOMER and delivery.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    if current_user.role == UserRole.DRIVER and delivery.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    return delivery


@router.patch("/{delivery_id}/assign-driver", response_model=DeliveryResponse)
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
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    driver = db.query(User).filter(
        User.id == payload.driver_id,
        User.role == UserRole.DRIVER,
        User.is_active == True,
    ).first()

    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found or inactive")

    delivery.driver_id = driver.id
    delivery.status = DeliveryStatus.ASSIGNED

    db.commit()
    db.refresh(delivery)

    return delivery


@router.patch("/{delivery_id}/status", response_model=DeliveryResponse)
def update_delivery_status(
    delivery_id: int,
    payload: UpdateDeliveryStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
            UserRole.DRIVER,
        )
    ),
):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    if current_user.role == UserRole.DRIVER and delivery.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    delivery.status = payload.status

    order = db.query(Order).filter(Order.id == delivery.order_id).first()

    if payload.status == DeliveryStatus.PICKED_UP:
        delivery.picked_up_at = datetime.utcnow()
        if order:
            order.status = OrderStatus.OUT_FOR_DELIVERY

    elif payload.status == DeliveryStatus.OUT_FOR_DELIVERY:
        if order:
            order.status = OrderStatus.OUT_FOR_DELIVERY

    elif payload.status == DeliveryStatus.DELIVERED:
        delivery.delivered_at = datetime.utcnow()
        if order:
            order.status = OrderStatus.DELIVERED

    elif payload.status == DeliveryStatus.FAILED:
        delivery.failure_reason = payload.failure_reason

    elif payload.status == DeliveryStatus.CANCELLED:
        if order:
            order.status = OrderStatus.CANCELLED

    db.commit()
    db.refresh(delivery)

    return delivery


@router.patch("/{delivery_id}/location", response_model=DeliveryResponse)
def update_driver_location(
    delivery_id: int,
    payload: UpdateDriverLocation,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DRIVER)),
):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    if delivery.driver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    delivery.current_latitude = payload.latitude
    delivery.current_longitude = payload.longitude

    db.commit()
    db.refresh(delivery)

    return delivery