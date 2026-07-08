from datetime import datetime
from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    meal_id: int | None = None
    plan_id: int | None = None
    order_id: int | None = None
    delivery_id: int | None = None
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = None


class ReviewUpdate(BaseModel):
    rating: int | None = Field(None, ge=1, le=5)
    comment: str | None = None


class ReviewResponse(BaseModel):
    id: int
    user_id: int
    meal_id: int | None
    plan_id: int | None
    order_id: int | None
    delivery_id: int | None
    rating: int
    comment: str | None
    created_at: datetime

    class Config:
        from_attributes = True