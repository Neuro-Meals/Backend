from datetime import datetime
from pydantic import BaseModel, Field


class MealCategoryCreate(BaseModel):
    name_en: str = Field(..., min_length=2, max_length=100)
    name_ar: str | None = None
    description: str | None = None


class MealCategoryUpdate(BaseModel):
    name_en: str | None = Field(None, min_length=2, max_length=100)
    name_ar: str | None = None
    description: str | None = None
    is_active: bool | None = None


class MealCategoryResponse(BaseModel):
    id: int
    name_en: str
    name_ar: str | None
    description: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
        
class MealCreate(BaseModel):
    category_id: int

    name_en: str = Field(..., min_length=2, max_length=150)
    name_ar: str | None = None

    description_en: str | None = None
    description_ar: str | None = None

    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float

    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None

    price: float
    image_url: str | None = None

    ingredients: list[str] | None = None
    allergens: list[str] | None = None
    diet_tags: list[str] | None = None

    is_available: bool = True


class MealUpdate(BaseModel):
    category_id: int | None = None

    name_en: str | None = None
    name_ar: str | None = None

    description_en: str | None = None
    description_ar: str | None = None

    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None

    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None

    price: float | None = None
    image_url: str | None = None

    ingredients: list[str] | None = None
    allergens: list[str] | None = None
    diet_tags: list[str] | None = None

    is_available: bool | None = None


class MealResponse(BaseModel):
    id: int
    category_id: int

    name_en: str
    name_ar: str | None

    description_en: str | None
    description_ar: str | None

    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float

    fiber_g: float | None
    sugar_g: float | None
    sodium_mg: float | None

    price: float
    image_url: str | None

    ingredients: list[str] | None
    allergens: list[str] | None
    diet_tags: list[str] | None

    is_available: bool
    created_at: datetime

    class Config:
        from_attributes = True        