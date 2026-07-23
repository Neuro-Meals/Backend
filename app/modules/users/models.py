from datetime import datetime, time
from enum import Enum

from sqlalchemy import (
    Boolean,
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class UserRole(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    NUTRITION_MANAGER = "nutrition_manager"
    DELIVERY_MANAGER = "delivery_manager"
    DRIVER = "driver"
    FINANCE_MANAGER = "finance_manager"
    CHEF = "chef"


class FitnessGoal(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    MAINTENANCE = "maintenance"
    HEALTHY_LIFESTYLE = "healthy_lifestyle"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class DeliveryPlaceType(str, Enum):
    HOME = "home"
    WORK = "work"
    GYM = "gym"
    SCHOOL = "school"
    UNIVERSITY = "university"
    OTHER = "other"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True,
        nullable=False,
    )

    phone: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        index=True,
        nullable=False,
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    gender: Mapped[Gender | None] = mapped_column(
        SqlEnum(
            Gender,
            name="gender",
        ),
        nullable=True,
    )

    age: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    height_cm: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    weight_kg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    fitness_goal: Mapped[FitnessGoal | None] = mapped_column(
        SqlEnum(
            FitnessGoal,
            name="fitnessgoal",
        ),
        nullable=True,
    )

    dietary_preference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    allergies: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            name="userrole",
        ),
        default=UserRole.CUSTOMER,
        nullable=False,
    )

    email_otp: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    email_otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    password_reset_otp: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    password_reset_otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
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

    delivery_preferences: Mapped[
        list["UserCategoryDeliveryPreference"]
    ] = relationship(
        "UserCategoryDeliveryPreference",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class UserCategoryDeliveryPreference(Base):
    __tablename__ = "user_category_delivery_preferences"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "meal_category_id",
            name="uq_user_category_delivery_preference",
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

    meal_category_id: Mapped[int] = mapped_column(
        ForeignKey(
            "meal_categories.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    place_type: Mapped[DeliveryPlaceType] = mapped_column(
        SqlEnum(
            DeliveryPlaceType,
            name="delivery_place_type",
        ),
        nullable=False,
    )

    place_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    city: Mapped[str] = mapped_column(
        String(100),
        default="Riyadh",
        server_default="Riyadh",
        nullable=False,
    )

    delivery_area: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    delivery_address: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    preferred_delivery_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    delivery_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
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

    user: Mapped["User"] = relationship(
        "User",
        back_populates="delivery_preferences",
    )