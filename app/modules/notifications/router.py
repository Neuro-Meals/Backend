from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.notifications.models import Notification, NotificationType
from app.modules.notifications.schemas import NotificationCreate, NotificationResponse
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("/", response_model=NotificationResponse)
def create_notification(
    payload: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)
    ),
):
    notification = Notification(**payload.model_dump())

    db.add(notification)
    db.commit()
    db.refresh(notification)

    return notification


@router.get("/my")
def my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    is_read: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    total = query.count()

    notifications = (
        query.order_by(Notification.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": notifications,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/")
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)
    ),
    search: str | None = Query(None),
    user_id: int | None = Query(None),
    notification_type: NotificationType | None = Query(None),
    is_read: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Notification)

    if search:
        value = f"%{search}%"
        query = query.filter(
            or_(
                Notification.title.ilike(value),
                Notification.message.ilike(value),
            )
        )

    if user_id:
        query = query.filter(Notification.user_id == user_id)

    if notification_type:
        query = query.filter(Notification.notification_type == notification_type)

    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    total = query.count()

    notifications = (
        query.order_by(Notification.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": notifications,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/{notification_id}", response_model=NotificationResponse)
def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = db.query(Notification).filter(Notification.id == notification_id).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if current_user.role == UserRole.CUSTOMER and notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    return notification


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = db.query(Notification).filter(Notification.id == notification_id).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if current_user.role == UserRole.CUSTOMER and notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    notification.is_read = True

    db.commit()
    db.refresh(notification)

    return notification


@router.patch("/my/read-all")
def mark_all_my_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).update({"is_read": True})

    db.commit()

    return {"message": "All notifications marked as read"}