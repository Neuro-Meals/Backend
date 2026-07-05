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