from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.users.models import UserRole


class UserCreate(BaseModel):
    first_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
    )
    last_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
    )
    phone: str = Field(
        ...,
        min_length=8,
        max_length=30,
    )
    email: EmailStr
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
    )

    location: str = Field(
        ...,
        min_length=2,
        max_length=150,
    )
    address: str = Field(
        ...,
        min_length=2,
        max_length=255,
    )


class VerifyEmailOTP(BaseModel):
    email: EmailStr
    otp: str = Field(
        ...,
        min_length=4,
        max_length=6,
    )


class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    phone: str

    location: str | None = None
    address: str | None = None

    role: UserRole
    is_verified: bool
    is_active: bool

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)