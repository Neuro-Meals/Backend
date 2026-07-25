from datetime import datetime
from pydantic import BaseModel, Field
from typing import List
from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Literal
from pydantic import BaseModel, Field, field_validator

MealTime = Literal[
    "breakfast",
    "lunch",
    "dinner",
    "snack",
]


class DayMealCategories(BaseModel):
    breakfast: List[int] = Field(default_factory=list)
    lunch: List[int] = Field(default_factory=list)
    dinner: List[int] = Field(default_factory=list)
    snack: List[int] = Field(default_factory=list)

    @field_validator(
        "breakfast",
        "lunch",
        "dinner",
        "snack",
    )
    @classmethod
    def remove_duplicate_meal_ids(
        cls,
        meal_ids: List[int],
    ) -> List[int]:
        # Keep the original order while removing duplicates.
        return list(dict.fromkeys(meal_ids))


class DayMealAssignmentRequest(BaseModel):
    subscription_id: int
    day_number: int = Field(ge=1)
    categories: DayMealCategories


class AssignedMealDetails(BaseModel):
    id: int
    category_id: int | None = None
    name_en: str | None = None
    name_ar: str | None = None
    description_en: str | None = None
    description_ar: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    image_url: str | None = None
    is_available: bool | None = None


class AssignedMealItem(BaseModel):
    selection_id: int
    subscription_id: int
    plan_id: int
    day_number: int
    meal_time: str
    is_skipped: bool
    skip_reason: str | None = None
    meal: AssignedMealDetails


class DayMealAssignmentResponse(BaseModel):
    success: bool
    message: str
    subscription_id: int
    day_number: int
    created_count: int
    deleted_count: int
    assigned_meals: Dict[str, List[AssignedMealItem]]
    
class MealSelectionCreate(BaseModel):
    subscription_id: int
    meal_id: int
    day_number: int = Field(..., ge=1)
    meal_time: str = Field(..., min_length=2, max_length=50)


class MealSelectionUpdate(BaseModel):
    meal_id: int | None = None
    is_skipped: bool | None = None
    skip_reason: str | None = None


class MealSelectionResponse(BaseModel):
    id: int
    user_id: int
    subscription_id: int
    plan_id: int
    meal_id: int
    day_number: int
    meal_time: str
    is_skipped: bool
    skip_reason: str | None
    created_at: datetime

    class Config:
        from_attributes = True
        
class MealAssignmentError(BaseModel):
    meal_id: int
    reason: str


class MealBulkAssignmentRequest(BaseModel):
    subscription_id: int = Field(gt=0)
    meal_ids: List[int] = Field(min_length=1)
    day_number: int = Field(default=1, ge=1)
    meal_time: str = Field(min_length=1, max_length=50)

    @field_validator("meal_ids")
    @classmethod
    def validate_meal_ids(cls, meal_ids: List[int]) -> List[int]:
        """
        Validate IDs and remove duplicates while preserving their order.
        Example: [4, 5, 4] becomes [4, 5].
        """
        cleaned_ids: List[int] = []

        for meal_id in meal_ids:
            if meal_id <= 0:
                raise ValueError("Every meal_id must be greater than zero")

            if meal_id not in cleaned_ids:
                cleaned_ids.append(meal_id)

        if not cleaned_ids:
            raise ValueError("At least one meal_id is required")

        return cleaned_ids

    @field_validator("meal_time")
    @classmethod
    def normalize_meal_time(cls, meal_time: str) -> str:
        value = meal_time.strip().lower()

        allowed_times = {
            "breakfast",
            "lunch",
            "dinner",
            "snack",
        }

        if value not in allowed_times:
            raise ValueError(
                "meal_time must be breakfast, lunch, dinner, or snack"
            )

        return value


class MealBulkAssignmentResponse(BaseModel):
    success: bool
    message: str
    subscription_id: int
    day_number: int
    meal_time: str
    requested_count: int
    created_count: int
    skipped_count: int
    created: List[MealSelectionResponse]
    errors: List[MealAssignmentError]        