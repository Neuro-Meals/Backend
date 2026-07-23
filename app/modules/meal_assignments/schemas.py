from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class MealAssignmentItemCreate(BaseModel):
    meal_category_id: int = Field(
        ...,
        ge=1,
    )

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

    assignments: list[MealAssignmentItemCreate] = Field(
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
                "The same meal category cannot be submitted more than once"
            )

        return self


class MealAssignmentUpdate(BaseModel):
    meal_id: int | None = Field(
        default=None,
        ge=1,
    )

    quantity: int | None = Field(
        default=None,
        ge=1,
        le=20,
    )

    notes: str | None = Field(
        default=None,
        max_length=500,
    )

    is_active: bool | None = None


class MealCategorySummary(BaseModel):
    id: int
    name_en: str
    name_ar: str | None = None
    image_url: str | None = None


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


class AssignedBySummary(BaseModel):
    id: int
    first_name: str
    last_name: str
    role: str


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


class SubscriptionSummary(BaseModel):
    id: int
    plan_id: int
    status: str
    payment_status: str
    start_date: datetime | None = None
    end_date: datetime | None = None


class MealAssignmentResponse(BaseModel):
    id: int

    user_id: int
    subscription_id: int
    meal_category_id: int
    meal_id: int

    delivery_date: date

    quantity: int
    notes: str | None

    assigned_by: int
    is_active: bool

    assigned_at: datetime
    updated_at: datetime

    category: MealCategorySummary | None = None
    meal: MealSummary | None = None
    customer: CustomerSummary | None = None
    assigned_by_user: AssignedBySummary | None = None
    subscription: SubscriptionSummary | None = None

    class Config:
        from_attributes = True


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


class KitchenDailyResponse(BaseModel):
    delivery_date: date
    total_assignments: int
    total_customers: int
    total_meal_quantity: int

    meals: list[KitchenMealSummary]
    assignments: list[MealAssignmentResponse]


class MealAssignmentDeleteResponse(BaseModel):
    success: bool
    message: str