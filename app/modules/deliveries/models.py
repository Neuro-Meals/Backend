from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SqlEnum, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


if TYPE_CHECKING:
    from app.modules.orders.models import Order
    from app.modules.users.models import User


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    PICKED_UP = "picked_up"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    order_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    driver_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    status: Mapped[DeliveryStatus] = mapped_column(
        SqlEnum(
            DeliveryStatus,
            name="deliverystatus",
        ),
        default=DeliveryStatus.PENDING,
        nullable=False,
    )

    delivery_address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    delivery_notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    picked_up_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
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

    #
    # These relationships are view-only because the current
    # database columns do not yet have SQL ForeignKey objects.
    #
    # They allow:
    #
    # delivery.order
    # delivery.customer
    # delivery.driver
    #
    # without changing the existing database schema.

    order: Mapped[Order | None] = relationship(
        "Order",
        primaryjoin=(
            "foreign(Delivery.order_id) == Order.id"
        ),
        viewonly=True,
        lazy="selectin",
    )

    customer: Mapped[User | None] = relationship(
        "User",
        primaryjoin=(
            "foreign(Delivery.user_id) == User.id"
        ),
        viewonly=True,
        lazy="selectin",
        overlaps="driver",
    )

    driver: Mapped[User | None] = relationship(
        "User",
        primaryjoin=(
            "foreign(Delivery.driver_id) == User.id"
        ),
        viewonly=True,
        lazy="selectin",
        overlaps="customer",
    )

    def __repr__(self) -> str:
        return (
            f"<Delivery("
            f"id={self.id}, "
            f"order_id={self.order_id}, "
            f"user_id={self.user_id}, "
            f"driver_id={self.driver_id}, "
            f"status={self.status}"
            f")>"
        )