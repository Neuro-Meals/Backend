from datetime import datetime
import json
from sqlalchemy import Boolean, DateTime, Float, Integer, String, JSON 
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MealCategory(Base):
    __tablename__ = "meal_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name_en: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    category_id: Mapped[int] = mapped_column(Integer, nullable=False)

    name_en: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    name_ar: Mapped[str | None] = mapped_column(String(150), nullable=True)

    description_en: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description_ar: Mapped[str | None] = mapped_column(String(500), nullable=True)

    calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)

    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    sugar_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    sodium_mg: Mapped[float | None] = mapped_column(Float, nullable=True)

    price: Mapped[float] = mapped_column(Float, nullable=False)

    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    ingredients: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    allergens: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    diet_tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )    