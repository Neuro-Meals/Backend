from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.coupons.models import DiscountType


class CouponCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    description: str | None = None
    discount_type: DiscountType
    discount_value: float = Field(..., gt=0)
    max_uses: int | None = Field(None, ge=1)
    max_uses_per_user: int | None = Field(None, ge=1)
    min_order_amount: float | None = Field(None, ge=0)
    applicable_plan_id: int | None = None
    allowed_user_id: int | None = None
    new_customers_only: bool = False
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool = True


class CouponUpdate(BaseModel):
    description: str | None = None
    discount_type: DiscountType | None = None
    discount_value: float | None = Field(None, gt=0)
    max_uses: int | None = Field(None, ge=1)
    max_uses_per_user: int | None = Field(None, ge=1)
    min_order_amount: float | None = Field(None, ge=0)
    applicable_plan_id: int | None = None
    allowed_user_id: int | None = None
    new_customers_only: bool | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None


class CouponValidateRequest(BaseModel):
    code: str
    amount: float = Field(..., ge=0)
    plan_id: int | None = None


class CouponResponse(BaseModel):
    id: int
    code: str
    description: str | None
    discount_type: str
    discount_value: float
    max_uses: int | None
    used_count: int
    max_uses_per_user: int | None = None
    min_order_amount: float | None
    applicable_plan_id: int | None = None
    allowed_user_id: int | None = None
    new_customers_only: bool = False
    source: str = "admin"
    starts_at: datetime | None
    expires_at: datetime | None
    is_active: bool
    created_at: datetime


class CouponRedemptionResponse(BaseModel):
    id: int
    coupon_id: int
    user_id: int
    subscription_id: int
    payment_id: int
    original_amount: float
    discount_amount: float
    final_amount: float
    redeemed_at: datetime

    class Config:
        from_attributes = True
