from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator


class MealAssignmentItemCreate(BaseModel):
    meal_id: int = Field(
        ...,
        ge=1,
    )

    quantity: int = Field(
        default=1,
        ge=1,
        le=20,
    )

    notes: str | None = Field(
        default=None,
        max_length=500,
    )


class MealCategoryAssignmentCreate(BaseModel):
    meal_category_id: int = Field(
        ...,
        ge=1,
    )

    delivery_preference_id: int = Field(
        ...,
        ge=1,
    )

    driver_id: int = Field(
        ...,
        ge=1,
    )

    delivery_time: time

    notes: str | None = Field(
        default=None,
        max_length=500,
    )

    meals: list[MealAssignmentItemCreate] = Field(
        ...,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_unique_meals(self):
        meal_ids = [
            item.meal_id
            for item in self.meals
        ]

        if len(meal_ids) != len(set(meal_ids)):
            raise ValueError(
                "The same meal cannot be selected more than once "
                "inside one meal category"
            )

        return self


class MealAssignmentBatchCreate(BaseModel):
    user_id: int = Field(
        ...,
        ge=1,
    )

    subscription_id: int = Field(
        ...,
        ge=1,
    )

    delivery_date: date

    assignments: list[MealCategoryAssignmentCreate] = Field(
        ...,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_unique_categories(self):
        category_ids = [
            assignment.meal_category_id
            for assignment in self.assignments
        ]

        if len(category_ids) != len(set(category_ids)):
            raise ValueError(
                "The same meal category cannot be submitted "
                "more than once for the same delivery date"
            )

        return self


class MealAssignmentItemUpdate(BaseModel):
    meal_id: int = Field(
        ...,
        ge=1,
    )

    quantity: int = Field(
        default=1,
        ge=1,
        le=20,
    )

    notes: str | None = Field(
        default=None,
        max_length=500,
    )


class MealAssignmentUpdate(BaseModel):
    delivery_preference_id: int | None = Field(
        default=None,
        ge=1,
    )

    driver_id: int | None = Field(
        default=None,
        ge=1,
    )

    delivery_time: time | None = None

    notes: str | None = Field(
        default=None,
        max_length=500,
    )

    is_active: bool | None = None

    meals: list[MealAssignmentItemUpdate] | None = Field(
        default=None,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_unique_meals(self):
        if self.meals is None:
            return self

        meal_ids = [
            item.meal_id
            for item in self.meals
        ]

        if len(meal_ids) != len(set(meal_ids)):
            raise ValueError(
                "The same meal cannot be selected more than once"
            )

        return self


class MealAssignmentDriverUpdate(BaseModel):
    driver_id: int = Field(
        ...,
        ge=1,
    )


class MealAssignmentDeliveryUpdate(BaseModel):
    delivery_preference_id: int = Field(
        ...,
        ge=1,
    )

    delivery_time: time | None = None


class MealCategorySummary(BaseModel):
    id: int
    name_en: str
    name_ar: str | None = None
    image_url: str | None = None

    model_config = {
        "from_attributes": True,
    }


class MealSummary(BaseModel):
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

    ingredients: list[str] = Field(
        default_factory=list,
    )

    allergens: list[str] = Field(
        default_factory=list,
    )

    diet_tags: list[str] = Field(
        default_factory=list,
    )

    model_config = {
        "from_attributes": True,
    }


class MealAssignmentItemResponse(BaseModel):
    id: int
    meal_assignment_id: int
    meal_id: int

    quantity: int
    notes: str | None = None

    created_at: datetime
    updated_at: datetime

    meal: MealSummary | None = None

    model_config = {
        "from_attributes": True,
    }


class AssignedBySummary(BaseModel):
    id: int
    first_name: str
    last_name: str
    role: str

    model_config = {
        "from_attributes": True,
    }


class DriverSummary(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    role: str
    is_active: bool

    model_config = {
        "from_attributes": True,
    }


class CustomerSummary(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None = None

    allergies: list[str] = Field(
        default_factory=list,
    )

    dietary_preference: str | None = None
    fitness_goal: str | None = None

    model_config = {
        "from_attributes": True,
    }


class SubscriptionSummary(BaseModel):
    id: int
    plan_id: int
    status: str
    payment_status: str
    start_date: datetime | None = None
    end_date: datetime | None = None

    model_config = {
        "from_attributes": True,
    }


class DeliveryPreferenceSummary(BaseModel):
    id: int
    user_id: int
    meal_category_id: int

    place_type: str | None = None
    place_name: str | None = None

    city: str | None = None
    delivery_area: str | None = None
    delivery_address: str | None = None

    latitude: float | None = None
    longitude: float | None = None

    preferred_delivery_time: time | None = None
    delivery_note: str | None = None

    is_active: bool

    model_config = {
        "from_attributes": True,
    }


class MealAssignmentResponse(BaseModel):
    id: int

    user_id: int
    subscription_id: int
    meal_category_id: int

    delivery_preference_id: int
    driver_id: int

    delivery_date: date
    delivery_time: time

    notes: str | None = None

    assigned_by: int
    is_active: bool

    assigned_at: datetime
    updated_at: datetime

    category: MealCategorySummary | None = None

    meals: list[MealAssignmentItemResponse] = Field(
        default_factory=list,
    )

    customer: CustomerSummary | None = None
    driver: DriverSummary | None = None
    assigned_by_user: AssignedBySummary | None = None
    subscription: SubscriptionSummary | None = None

    delivery_preference: (
        DeliveryPreferenceSummary | None
    ) = None

    model_config = {
        "from_attributes": True,
    }


class MealAssignmentDateGroup(BaseModel):
    delivery_date: date
    total_assignments: int
    assignments: list[MealAssignmentResponse]


class MealAssignmentBatchResponse(BaseModel):
    success: bool
    message: str

    created_count: int
    updated_count: int

    delivery_date: date
    user_id: int
    subscription_id: int

    data: list[MealAssignmentResponse]


class MealAssignmentListResponse(BaseModel):
    data: list[MealAssignmentResponse]

    total: int
    page: int
    limit: int
    pages: int


class KitchenMealSummary(BaseModel):
    meal_id: int
    meal_name: str
    meal_name_ar: str | None = None

    meal_category_id: int
    category_name: str | None = None
    category_name_ar: str | None = None

    total_quantity: int
    customer_count: int


class KitchenCategorySummary(BaseModel):
    meal_category_id: int
    category_name: str
    category_name_ar: str | None = None

    assignment_count: int
    customer_count: int
    total_meal_quantity: int

    meals: list[KitchenMealSummary]


class KitchenDailyResponse(BaseModel):
    delivery_date: date
    total_assignments: int
    total_customers: int
    total_meal_quantity: int

    categories: list[KitchenCategorySummary]
    assignments: list[MealAssignmentResponse]


class MealAssignmentDeleteResponse(BaseModel):
    success: bool
    message: str