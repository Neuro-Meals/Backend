from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


if TYPE_CHECKING:
    from app.modules.orders.models import Order


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    READY_FOR_PICKUP = "ready_for_pickup"
    PICKED_UP = "picked_up"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Delivery(Base):
    """
    Tracking record for one Order.

    Business delivery data such as customer, driver, address,
    delivery date, and delivery time remains on Order.
    """

    __tablename__ = "deliveries"

    __table_args__ = (
        UniqueConstraint(
            "order_id",
            name="uq_delivery_order_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey(
            "orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[DeliveryStatus] = mapped_column(
        SqlEnum(
            DeliveryStatus,
            name="deliverystatus",
        ),
        default=DeliveryStatus.PENDING,
        nullable=False,
        index=True,
    )

    ready_for_pickup_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    picked_up_at: Mapped[datetime | None] = mapped_column(
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

    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    current_latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    current_longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
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

    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="delivery",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Delivery("
            f"id={self.id}, "
            f"order_id={self.order_id}, "
            f"status={self.status}"
            f")>"
        )