from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.modules.referrals.models import (
    ReferralCommissionScope,
    ReferralRewardMode,
)


class ReferralProgramSettingUpdate(BaseModel):
    is_active: bool | None = None

    reward_mode: ReferralRewardMode | None = None

    # Fixed SAR amount or percentage number depending on reward_mode.
    # Examples: 50 = SAR 50, or 5 = 5%.
    reward_value: float | None = Field(None, gt=0)

    commission_scope: ReferralCommissionScope | None = None

    max_reward_per_payment: float | None = Field(
        None,
        gt=0,
    )

    reward_expiry_days: int | None = Field(
        None,
        ge=1,
        le=3650,
    )

    # Backwards compatibility with the first frontend version.
    reward_amount: float | None = Field(None, gt=0)
    referred_customer_must_make_first_payment: bool | None = None

    @model_validator(mode="after")
    def normalize_legacy_fields(self):
        if (
            self.reward_value is None
            and self.reward_amount is not None
        ):
            self.reward_value = self.reward_amount

        if self.reward_mode == ReferralRewardMode.FIXED_FIRST_PAYMENT:
            self.commission_scope = (
                ReferralCommissionScope.FIRST_PAYMENT_ONLY
            )

        return self


class ReferralProgramSettingResponse(BaseModel):
    id: int
    is_active: bool
    reward_mode: str
    reward_value: float
    commission_scope: str
    max_reward_per_payment: float | None
    reward_expiry_days: int

    # Legacy compatibility.
    reward_amount: float
    referred_customer_must_make_first_payment: bool

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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


class ReferralEarningResponse(BaseModel):
    id: int
    referral_id: int
    referral_code_id: int
    referrer_user_id: int
    referred_user_id: int
    subscription_id: int
    payment_id: int
    coupon_id: int | None

    reward_mode: str
    reward_rate: float
    payment_amount: float
    reward_amount: float

    status: str
    expires_at: datetime | None
    used_at: datetime | None
    earned_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True
