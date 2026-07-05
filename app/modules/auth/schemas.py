from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CurrentSubscriptionResponse(BaseModel):
    id: int
    plan_id: int
    plan_name: str | None
    status: str
    payment_status: str
    amount: float
    start_date: datetime | None
    end_date: datetime | None


class LoggedInUser(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    role: str
    permissions: list[str]

    gender: str | None
    age: int | None
    height_cm: float | None
    weight_kg: float | None
    fitness_goal: str | None
    dietary_preference: str | None
    allergies: list[str] | None

    subscription: CurrentSubscriptionResponse | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: LoggedInUser


class ResendVerificationOTP(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=4, max_length=6)
    new_password: str = Field(..., min_length=6)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)