from datetime import datetime
from pydantic import BaseModel, Field


class ReferralProgramSettingUpdate(BaseModel):
    is_active: bool | None = None
    reward_amount: float | None = Field(None, gt=0)
    reward_expiry_days: int | None = Field(None, ge=1, le=3650)
    referred_customer_must_make_first_payment: bool | None = None


class ReferralCodeResponse(BaseModel):
    code: str
    is_active: bool


class ReferralRewardResponse(BaseModel):
    id: int
    coupon_id: int | None
    reward_type: str
    reward_value: float
    status: str
    expires_at: datetime | None
    used_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
