from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class CurrentSubscriptionResponse(BaseModel):
    id: int
    plan_id: int
    plan_name: str | None = None
    status: str
    payment_status: str
    amount: float
    start_date: datetime | None = None
    end_date: datetime | None = None


class LoggedInUser(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    role: str
    permissions: list[str]

    location: str | None = None
    address: str | None = None

    gender: str | None = None
    age: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    fitness_goal: str | None = None
    dietary_preference: str | None = None
    allergies: list[str] | None = None

    subscription: CurrentSubscriptionResponse | None = None


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
    new_password: str = Field(..., min_length=6, max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)