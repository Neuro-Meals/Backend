from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class OrderStatus(str, Enum):
    SCHEDULED = "scheduled"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY_FOR_DELIVERY = "ready_for_delivery"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class OrderSource(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"


class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "delivery_date",
            name="uq_order_subscription_delivery_date",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "subscriptions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "meal_plans.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    order_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    source: Mapped[OrderSource] = mapped_column(
        SqlEnum(
            OrderSource,
            name="order_source",
        ),
        default=OrderSource.AUTOMATIC,
        server_default=OrderSource.AUTOMATIC.value,
        nullable=False,
    )

    status: Mapped[OrderStatus] = mapped_column(
        SqlEnum(
            OrderStatus,
            name="orderstatus",
        ),
        default=OrderStatus.PENDING,
        server_default=OrderStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    total_amount: Mapped[float] = mapped_column(
        Float,
        default=0,
        server_default="0",
        nullable=False,
    )

    delivery_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )

    delivery_preference_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "user_category_delivery_preferences.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    delivery_place_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    delivery_place_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    delivery_city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    delivery_area: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    delivery_address: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    delivery_latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    delivery_longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    delivery_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    items: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    preparation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    ready_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    out_for_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    cancellation_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )