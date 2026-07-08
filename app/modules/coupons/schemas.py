from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.coupons.models import DiscountType


class CouponCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    description: str | None = None
    discount_type: DiscountType
    discount_value: float = Field(..., gt=0)
    max_uses: int | None = None
    min_order_amount: float | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool = True


class CouponUpdate(BaseModel):
    description: str | None = None
    discount_type: DiscountType | None = None
    discount_value: float | None = Field(None, gt=0)
    max_uses: int | None = None
    min_order_amount: float | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None


class CouponValidateRequest(BaseModel):
    code: str
    amount: float = Field(..., ge=0)


class CouponResponse(BaseModel):
    id: int
    code: str
    description: str | None
    discount_type: str
    discount_value: float
    max_uses: int | None
    used_count: int
    min_order_amount: float | None
    starts_at: datetime | None
    expires_at: datetime | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True