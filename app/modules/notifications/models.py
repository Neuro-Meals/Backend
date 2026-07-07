from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NotificationType(str, Enum):
    GENERAL = "general"
    ORDER = "order"
    DELIVERY = "delivery"
    SUBSCRIPTION = "subscription"
    PAYMENT = "payment"
    PROMOTION = "promotion"


class NotificationChannel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)

    notification_type: Mapped[NotificationType] = mapped_column(
        SqlEnum(NotificationType),
        default=NotificationType.GENERAL,
        nullable=False,
    )

    channel: Mapped[NotificationChannel] = mapped_column(
        SqlEnum(NotificationChannel),
        default=NotificationChannel.IN_APP,
        nullable=False,
    )

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)