from __future__ import annotations

from datetime import date, time
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class MenuGenerationMode(str, Enum):
    SINGLE_DAY = "single_day"
    REPEAT_WEEK = "repeat_week"
    CUSTOM_WEEKS = "custom_weeks"


class MealCategoryAssignment(BaseModel):
    """
    Menu details for one meal category on one subscription day.

    The delivery preference and delivery time are resolved by the backend
    from the customer's active preference for this category. The admin only
    selects meals and the planned driver.

    An empty meal_ids list means that the category is not assigned for that
    day. In that case driver_id must be null.
    """

    meal_ids: list[int] = Field(default_factory=list)
    driver_id: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("meal_ids")
    @classmethod
    def validate_meal_ids(cls, meal_ids: list[int]) -> list[int]:
        unique_ids: list[int] = []
        seen: set[int] = set()

        for meal_id in meal_ids:
            if meal_id <= 0:
                raise ValueError("Every meal ID must be a positive integer")

            if meal_id not in seen:
                seen.add(meal_id)
                unique_ids.append(meal_id)

        return unique_ids

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_driver_requirement(self):
        if self.meal_ids and self.driver_id is None:
            raise ValueError(
                "driver_id is required when meals are selected"
            )

        if not self.meal_ids and self.driver_id is not None:
            raise ValueError(
                "driver_id must be null when no meals are selected"
            )

        return self

    @property
    def is_assigned(self) -> bool:
        return bool(self.meal_ids)


class MealCategories(BaseModel):
    breakfast: MealCategoryAssignment = Field(
        default_factory=MealCategoryAssignment
    )
    lunch: MealCategoryAssignment = Field(
        default_factory=MealCategoryAssignment
    )
    dinner: MealCategoryAssignment = Field(
        default_factory=MealCategoryAssignment
    )
    snack: MealCategoryAssignment = Field(
        default_factory=MealCategoryAssignment
    )

    def assignment_count(self) -> int:
        return sum(
            len(category.meal_ids)
            for category in (
                self.breakfast,
                self.lunch,
                self.dinner,
                self.snack,
            )
        )

    def active_category_count(self) -> int:
        return sum(
            category.is_assigned
            for category in (
                self.breakfast,
                self.lunch,
                self.dinner,
                self.snack,
            )
        )


class DayMenu(BaseModel):
    """
    In weekly modes day_number is the position inside the subscription week,
    not a weekday name.
    """

    day_number: int = Field(ge=1, le=7)
    categories: MealCategories


class SingleDayConfiguration(BaseModel):
    """day_number is the absolute subscription day."""

    day_number: int = Field(ge=1)
    categories: MealCategories


class RepeatWeekConfiguration(BaseModel):
    days: list[DayMenu] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def validate_complete_week(self):
        submitted_days = [day.day_number for day in self.days]

        if len(submitted_days) != len(set(submitted_days)):
            raise ValueError(
                "The repeating week contains duplicate day numbers"
            )

        expected_days = set(range(1, 8))
        received_days = set(submitted_days)

        if received_days != expected_days:
            missing = sorted(expected_days - received_days)
            unexpected = sorted(received_days - expected_days)
            raise ValueError(
                "A repeating weekly template must contain days 1 through 7. "
                f"Missing={missing}, unexpected={unexpected}"
            )

        self.days.sort(key=lambda day: day.day_number)
        return self


class CustomWeek(BaseModel):
    week_number: int = Field(ge=1)
    days: list[DayMenu] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def validate_week_days(self):
        day_numbers = [day.day_number for day in self.days]

        if len(day_numbers) != len(set(day_numbers)):
            raise ValueError(
                f"Week {self.week_number} contains duplicate day numbers"
            )

        self.days.sort(key=lambda day: day.day_number)
        return self


class CustomWeeksConfiguration(BaseModel):
    weeks: list[CustomWeek] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_weeks(self):
        week_numbers = [week.week_number for week in self.weeks]

        if len(week_numbers) != len(set(week_numbers)):
            raise ValueError("custom_weeks contains duplicate week numbers")

        self.weeks.sort(key=lambda week: week.week_number)
        return self


class MenuGenerationRequest(BaseModel):
    mode: MenuGenerationMode
    replace_existing: bool = True

    single_day: SingleDayConfiguration | None = None
    repeat_week: RepeatWeekConfiguration | None = None
    custom_weeks: CustomWeeksConfiguration | None = None

    @model_validator(mode="after")
    def validate_selected_configuration(self):
        configurations = {
            MenuGenerationMode.SINGLE_DAY: self.single_day,
            MenuGenerationMode.REPEAT_WEEK: self.repeat_week,
            MenuGenerationMode.CUSTOM_WEEKS: self.custom_weeks,
        }

        selected_configuration = configurations[self.mode]

        if selected_configuration is None:
            raise ValueError(
                f"The '{self.mode.value}' configuration is required when "
                f"mode is '{self.mode.value}'"
            )

        supplied_configurations = [
            name.value
            for name, configuration in configurations.items()
            if configuration is not None
        ]

        if len(supplied_configurations) != 1:
            raise ValueError(
                "Provide only the configuration matching the selected mode. "
                f"Received: {supplied_configurations}"
            )

        return self


class GeneratedMealDetails(BaseModel):
    id: int
    category_id: int
    name_en: str
    name_ar: str | None = None
    description_en: str | None = None
    description_ar: str | None = None
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None
    price: float
    image_url: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    diet_tags: list[str] = Field(default_factory=list)


class GeneratedMealItem(BaseModel):
    item_id: int
    meal_id: int
    quantity: int
    notes: str | None = None
    meal: GeneratedMealDetails


class GeneratedDriver(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None


class GeneratedDeliveryPreference(BaseModel):
    id: int
    meal_category_id: int
    place_type: str | None = None
    place_name: str | None = None
    city: str | None = None
    delivery_area: str | None = None
    delivery_address: str
    latitude: float | None = None
    longitude: float | None = None
    preferred_delivery_time: time
    delivery_note: str | None = None


class GeneratedCategoryAssignment(BaseModel):
    assignment_id: int
    meal_time: str
    meal_category_id: int
    category_name: str | None = None
    category_name_ar: str | None = None
    delivery_date: date
    delivery_time: time
    notes: str | None = None
    is_active: bool
    driver: GeneratedDriver
    delivery_preference: GeneratedDeliveryPreference
    meals: list[GeneratedMealItem] = Field(default_factory=list)


class GeneratedDay(BaseModel):
    day_number: int
    scheduled_date: date
    assignments: dict[str, GeneratedCategoryAssignment]


class MenuGenerationResponse(BaseModel):
    success: bool
    message: str
    mode: MenuGenerationMode
    subscription_id: int
    user_id: int
    plan_id: int
    subscription_days: int
    generated_day_count: int
    replace_existing: bool
    requested_assignment_count: int
    requested_category_count: int
    created_count: int
    updated_count: int
    deleted_count: int
    skipped_count: int
    generated_days: list[GeneratedDay]