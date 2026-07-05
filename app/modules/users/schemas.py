from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from app.modules.users.models import UserRole, FitnessGoal, Gender


class UserCreate(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=8)

    password: str = Field(..., min_length=6)

    location: str | None = None
    address: str | None = None

    gender: Gender | None = None
    age: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None

    fitness_goal: FitnessGoal | None = None
    dietary_preference: str | None = None
    allergies: list[str] | None = None


class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    location: str | None
    address: str | None
    gender: Gender | None
    age: int | None
    height_cm: float | None
    weight_kg: float | None
    fitness_goal: FitnessGoal | None
    dietary_preference: str | None
    allergies: list[str] | None = None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdateRole(BaseModel):
    role: UserRole


class VerifyEmailOTP(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=4, max_length=6)