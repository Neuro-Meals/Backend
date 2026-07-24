from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


if TYPE_CHECKING:
    from app.modules.meal_assignments.models import MealAssignment
    from app.modules.meals.models import MealCategory
    from app.modules.plans.models import MealPlan
    from app.modules.subscriptions.models import Subscription
    from app.modules.users.models import (
        User,
        UserCategoryDeliveryPreference,
    )


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
    """
    One order represents exactly one meal-category assignment.

    Example:

    Breakfast assignment
        - Banana
        - Eggs
        - Oatmeal
        - Home location
        - Driver John

    creates one breakfast order.

    Lunch and dinner create separate orders.
    """

    __tablename__ = "orders"

    __table_args__ = (
        UniqueConstraint(
            "meal_assignment_id",
            name="uq_order_meal_assignment",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    order_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
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

    meal_assignment_id: Mapped[int] = mapped_column(
        ForeignKey(
            "meal_assignments.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    meal_category_id: Mapped[int] = mapped_column(
        ForeignKey(
            "meal_categories.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    driver_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    delivery_preference_id: Mapped[int] = mapped_column(
        ForeignKey(
            "user_category_delivery_preferences.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    source: Mapped[OrderSource] = mapped_column(
        SqlEnum(
            OrderSource,
            name="order_source",
        ),
        default=OrderSource.AUTOMATIC,
        server_default=text("'AUTOMATIC'"),
        nullable=False,
        index=True,
    )

    status: Mapped[OrderStatus] = mapped_column(
        SqlEnum(
            OrderStatus,
            name="orderstatus",
        ),
        default=OrderStatus.SCHEDULED,
        server_default=text("'SCHEDULED'"),
        nullable=False,
        index=True,
    )

    delivery_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    delivery_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        index=True,
    )

    total_amount: Mapped[float] = mapped_column(
        Float,
        default=0,
        server_default="0",
        nullable=False,
    )

    items: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    #
    # Delivery-location snapshot
    #
    # These values are copied from the selected customer
    # delivery preference when the order is generated.
    #
    # Future changes to the customer's profile or preference
    # will not change old orders.
    #

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

    delivery_address: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
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

    #
    # Chef workflow timestamps
    #

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

    #
    # Driver workflow timestamps
    #

    out_for_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    #
    # Cancellation
    #

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

    #
    # Relationships
    #

    customer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )

    driver: Mapped["User"] = relationship(
        "User",
        foreign_keys=[driver_id],
        lazy="selectin",
    )

    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription",
        lazy="selectin",
    )

    plan: Mapped["MealPlan | None"] = relationship(
        "MealPlan",
        lazy="selectin",
    )

    meal_assignment: Mapped["MealAssignment"] = relationship(
        "MealAssignment",
        lazy="selectin",
    )

    meal_category: Mapped["MealCategory"] = relationship(
        "MealCategory",
        lazy="selectin",
    )

    delivery_preference: Mapped[
        "UserCategoryDeliveryPreference"
    ] = relationship(
        "UserCategoryDeliveryPreference",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            "<Order("
            f"id={self.id}, "
            f"order_number={self.order_number}, "
            f"user_id={self.user_id}, "
            f"meal_assignment_id={self.meal_assignment_id}, "
            f"meal_category_id={self.meal_category_id}, "
            f"driver_id={self.driver_id}, "
            f"delivery_date={self.delivery_date}, "
            f"status={self.status}"
            ")>"
        )