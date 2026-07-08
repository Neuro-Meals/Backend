from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    meal_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    delivery_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)