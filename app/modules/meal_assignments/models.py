from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


if TYPE_CHECKING:
    from app.modules.meals.models import Meal, MealCategory
    from app.modules.subscriptions.models import Subscription
    from app.modules.users.models import (
        User,
        UserCategoryDeliveryPreference,
    )


class MealAssignment(Base):
    """
    One MealAssignment represents one meal category assigned
    to one customer for one delivery date.

    Examples:

    Breakfast:
        - Banana
        - Eggs
        - Oatmeal
        - Home delivery preference
        - Driver John
        - 07:30

    Lunch:
        - Rice
        - Chicken
        - Vegetables
        - Office delivery preference
        - Driver Peter
        - 13:00
    """

    __tablename__ = "meal_assignments"

    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "delivery_date",
            "meal_category_id",
            name="uq_assignment_subscription_date_category",
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

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey(
            "subscriptions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
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

    delivery_preference_id: Mapped[int] = mapped_column(
        ForeignKey(
            "user_category_delivery_preferences.id",
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

    delivery_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    delivery_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    assigned_by: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        index=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(
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

    items: Mapped[list["MealAssignmentItem"]] = relationship(
        "MealAssignmentItem",
        back_populates="assignment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="MealAssignmentItem.id",
    )

    category: Mapped["MealCategory"] = relationship(
        "MealCategory",
        lazy="selectin",
    )

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

    assigned_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[assigned_by],
        lazy="selectin",
    )

    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
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
            "<MealAssignment("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"subscription_id={self.subscription_id}, "
            f"meal_category_id={self.meal_category_id}, "
            f"driver_id={self.driver_id}, "
            f"delivery_date={self.delivery_date}"
            ")>"
        )


class MealAssignmentItem(Base):
    """
    Stores the individual foods selected under a category.

    One breakfast assignment may contain several items:
    Banana, Eggs and Oatmeal.
    """

    __tablename__ = "meal_assignment_items"

    __table_args__ = (
        UniqueConstraint(
            "meal_assignment_id",
            "meal_id",
            name="uq_meal_assignment_item_meal",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    meal_assignment_id: Mapped[int] = mapped_column(
        ForeignKey(
            "meal_assignments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    meal_id: Mapped[int] = mapped_column(
        ForeignKey(
            "meals.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
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

    assignment: Mapped["MealAssignment"] = relationship(
        "MealAssignment",
        back_populates="items",
    )

    meal: Mapped["Meal"] = relationship(
        "Meal",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            "<MealAssignmentItem("
            f"id={self.id}, "
            f"meal_assignment_id={self.meal_assignment_id}, "
            f"meal_id={self.meal_id}, "
            f"quantity={self.quantity}"
            ")>"
        )