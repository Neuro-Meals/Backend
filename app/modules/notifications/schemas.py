from datetime import datetime
from pydantic import BaseModel, Field

from app.modules.notifications.models import NotificationChannel, NotificationType


class NotificationCreate(BaseModel):
    user_id: int
    title: str = Field(..., min_length=2, max_length=150)
    message: str = Field(..., min_length=2, max_length=1000)
    notification_type: NotificationType = NotificationType.GENERAL
    channel: NotificationChannel = NotificationChannel.IN_APP


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    notification_type: NotificationType
    channel: NotificationChannel
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True