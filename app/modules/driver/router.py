from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.deliveries.models import Delivery, DeliveryStatus
from app.modules.deliveries.schemas import DeliveryResponse, UpdateDriverLocation
from app.modules.orders.models import Order, OrderStatus
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/driver", tags=["Driver App"])


def get_driver_delivery(
    db: Session,
    delivery_id: int,
    driver_id: int,
) -> Delivery:
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.driver_id == driver_id,
    ).first()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found for this driver")

    return delivery


@router.get("/deliveries", response_model=list[DeliveryResponse])
def my_driver_deliveries(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DRIVER)),
):
    return (
        db.query(Delivery)
        .filter(Delivery.driver_id == current_user.id)
        .order_by(Delivery.id.desc())
        .all()
    )


@router.get("/deliveries/{delivery_id}", response_model=DeliveryResponse)
def get_my_driver_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DRIVER)),
):
    return get_driver_delivery(db, delivery_id, current_user.id)


@router.post("/deliveries/{delivery_id}/pickup", response_model=DeliveryResponse)
def pickup_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DRIVER)),
):
    delivery = get_driver_delivery(db, delivery_id, current_user.id)

    if delivery.status not in [DeliveryStatus.ASSIGNED, DeliveryStatus.PENDING]:
        raise HTTPException(status_code=400, detail="Delivery cannot be picked up now")

    delivery.status = DeliveryStatus.PICKED_UP
    delivery.picked_up_at = datetime.utcnow()

    order = db.query(Order).filter(Order.id == delivery.order_id).first()
    if order:
        order.status = OrderStatus.OUT_FOR_DELIVERY

    db.commit()
    db.refresh(delivery)

    return delivery


@router.post("/deliveries/{delivery_id}/out-for-delivery", response_model=DeliveryResponse)
def out_for_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DRIVER)),
):
    delivery = get_driver_delivery(db, delivery_id, current_user.id)

    if delivery.status not in [DeliveryStatus.PICKED_UP, DeliveryStatus.ASSIGNED]:
        raise HTTPException(status_code=400, detail="Delivery cannot be moved out for delivery")

    delivery.status = DeliveryStatus.OUT_FOR_DELIVERY

    order = db.query(Order).filter(Order.id == delivery.order_id).first()
    if order:
        order.status = OrderStatus.OUT_FOR_DELIVERY

    db.commit()
    db.refresh(delivery)

    return delivery


@router.post("/deliveries/{delivery_id}/complete", response_model=DeliveryResponse)
def complete_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DRIVER)),
):
    delivery = get_driver_delivery(db, delivery_id, current_user.id)

    if delivery.status not in [
        DeliveryStatus.OUT_FOR_DELIVERY,
        DeliveryStatus.PICKED_UP,
    ]:
        raise HTTPException(status_code=400, detail="Delivery cannot be completed now")

    delivery.status = DeliveryStatus.DELIVERED
    delivery.delivered_at = datetime.utcnow()

    order = db.query(Order).filter(Order.id == delivery.order_id).first()
    if order:
        order.status = OrderStatus.DELIVERED

    db.commit()
    db.refresh(delivery)

    return delivery


@router.post("/deliveries/{delivery_id}/fail", response_model=DeliveryResponse)
def fail_delivery(
    delivery_id: int,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DRIVER)),
):
    delivery = get_driver_delivery(db, delivery_id, current_user.id)

    if delivery.status == DeliveryStatus.DELIVERED:
        raise HTTPException(status_code=400, detail="Delivered order cannot be failed")

    delivery.status = DeliveryStatus.FAILED
    delivery.failure_reason = reason

    db.commit()
    db.refresh(delivery)

    return delivery


@router.patch("/deliveries/{delivery_id}/location", response_model=DeliveryResponse)
def update_delivery_location(
    delivery_id: int,
    payload: UpdateDriverLocation,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DRIVER)),
):
    delivery = get_driver_delivery(db, delivery_id, current_user.id)

    delivery.current_latitude = payload.latitude
    delivery.current_longitude = payload.longitude

    db.commit()
    db.refresh(delivery)

    return delivery