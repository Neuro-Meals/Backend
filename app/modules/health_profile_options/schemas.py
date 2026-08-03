from datetime import datetime
from enum import Enum
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthProfileOptionType(str, Enum):
    DIETARY_PREFERENCE = "dietary_preference"
    ALLERGY = "allergy"
    HEALTH_CONDITION = "health_condition"


_VALUE_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


class HealthProfileOptionBase(BaseModel):
    option_type: HealthProfileOptionType
    value: str = Field(..., min_length=1, max_length=100)
    label_en: str = Field(..., min_length=1, max_length=150)
    label_ar: str | None = Field(None, max_length=150)
    description: str | None = Field(None, max_length=1000)
    is_active: bool = True
    sort_order: int = Field(0, ge=0, le=100000)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _VALUE_PATTERN.fullmatch(normalized):
            raise ValueError(
                "value must use lowercase letters, numbers and underscores only"
            )
        return normalized

    @field_validator("label_en")
    @classmethod
    def normalize_label_en(cls, value: str) -> str:
        return value.strip()

    @field_validator("label_ar", "description")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class HealthProfileOptionCreate(HealthProfileOptionBase):
    pass


class HealthProfileOptionUpdate(BaseModel):
    option_type: HealthProfileOptionType | None = None
    value: str | None = Field(None, min_length=1, max_length=100)
    label_en: str | None = Field(None, min_length=1, max_length=150)
    label_ar: str | None = Field(None, max_length=150)
    description: str | None = Field(None, max_length=1000)
    is_active: bool | None = None
    sort_order: int | None = Field(None, ge=0, le=100000)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _VALUE_PATTERN.fullmatch(normalized):
            raise ValueError(
                "value must use lowercase letters, numbers and underscores only"
            )
        return normalized

    @field_validator("label_en")
    @classmethod
    def normalize_label_en(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("label_ar", "description")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class HealthProfileOptionStatusUpdate(BaseModel):
    is_active: bool


class HealthProfileOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    option_type: HealthProfileOptionType
    value: str
    label_en: str
    label_ar: str | None
    description: str | None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class PublicHealthProfileOptionsResponse(BaseModel):
    dietary_preferences: list[HealthProfileOptionResponse]
    allergies: list[HealthProfileOptionResponse]
    health_conditions: list[HealthProfileOptionResponse]
