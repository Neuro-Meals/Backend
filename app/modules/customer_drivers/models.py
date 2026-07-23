from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CustomerDriverAssignment(Base):
    """
    Stores the dedicated driver assigned to a customer.

    Business rules:

    1. One customer can have only one active driver.
    2. One driver can serve multiple customers.
    3. Old assignments are kept as history by setting
       is_active=False instead of deleting them permanently.
    """

    __tablename__ = "customer_driver_assignments"

    __table_args__ = (
        Index(
            "uq_customer_driver_active_customer",
            "customer_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "ix_customer_driver_active_driver",
            "driver_id",
            "is_active",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
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

    assigned_by: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    assignment_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        index=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    customer = relationship(
        "User",
        foreign_keys=[customer_id],
        lazy="joined",
    )

    driver = relationship(
        "User",
        foreign_keys=[driver_id],
        lazy="joined",
    )

    assigned_by_user = relationship(
        "User",
        foreign_keys=[assigned_by],
        lazy="joined",
    )