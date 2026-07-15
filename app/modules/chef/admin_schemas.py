from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ChefCreate(BaseModel):
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
    email: EmailStr
    phone: str = Field(
        ...,
        min_length=8,
        max_length=30,
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
    )

    location: str | None = Field(
        default=None,
        max_length=150,
    )
    address: str | None = Field(
        default=None,
        max_length=255,
    )


class ChefUpdate(BaseModel):
    first_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )
    last_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )
    email: EmailStr | None = None
    phone: str | None = Field(
        default=None,
        min_length=8,
        max_length=30,
    )
    location: str | None = Field(
        default=None,
        max_length=150,
    )
    address: str | None = Field(
        default=None,
        max_length=255,
    )
    is_active: bool | None = None


class AssignChefRoleRequest(BaseModel):
    user_id: int = Field(..., ge=1)


class ChefResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    full_name: str

    email: EmailStr
    phone: str

    location: str | None = None
    address: str | None = None

    role: str
    is_active: bool
    is_verified: bool

    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)