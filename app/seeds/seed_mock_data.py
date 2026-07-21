from __future__ import annotations
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar

from dotenv import dotenv_values
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.database import SessionLocal

from app.modules.users.models import User, UserRole

from app.modules.meals.models import (
    Meal,
    MealCategory,
)

from app.modules.plans.models import (
    DeliveryTemperature,
    DeliveryType,
    MealPlan,
    MealTime,
    PlanGoal,
    PlanType,
)

from app.modules.plan_menu.models import (
    PlanMenuItem,
    WeekDay,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_ENV_FILE = PROJECT_ROOT / ".env.seed"

seed_config = dotenv_values(SEED_ENV_FILE)


def get_required_setting(name: str) -> str:
    value = seed_config.get(name)

    if value is None or not str(value).strip():
        raise RuntimeError(
            f"Missing required setting '{name}' in {SEED_ENV_FILE}"
        )

    return str(value).strip()


def get_optional_setting(
    name: str,
    default: str,
) -> str:
    value = seed_config.get(name)

    if value is None or not str(value).strip():
        return default

    return str(value).strip()

SUPER_ADMIN_FIRST_NAME = get_optional_setting(
    "SEED_SUPER_ADMIN_FIRST_NAME",
    "Super",
)

SUPER_ADMIN_LAST_NAME = get_optional_setting(
    "SEED_SUPER_ADMIN_LAST_NAME",
    "Admin",
)

SUPER_ADMIN_EMAIL = get_required_setting(
    "SEED_SUPER_ADMIN_EMAIL",
).lower()

SUPER_ADMIN_PHONE = get_required_setting(
    "SEED_SUPER_ADMIN_PHONE",
)

SUPER_ADMIN_PASSWORD = get_required_setting(
    "SEED_SUPER_ADMIN_PASSWORD",
)


ADMIN_FIRST_NAME = get_optional_setting(
    "SEED_ADMIN_FIRST_NAME",
    "System",
)

ADMIN_LAST_NAME = get_optional_setting(
    "SEED_ADMIN_LAST_NAME",
    "Admin",
)

ADMIN_EMAIL = get_required_setting(
    "SEED_ADMIN_EMAIL",
).lower()

ADMIN_PHONE = get_required_setting(
    "SEED_ADMIN_PHONE",
)

ADMIN_PASSWORD = get_required_setting(
    "SEED_ADMIN_PASSWORD",
)

CATEGORY_DATA = [
    {
        "name_en": "Carbohydrates",
        "name_ar": "الكربوهيدرات",
        "description": (
            "Rice, pasta and potato meal options."
        ),
        "image_url": None,
        "is_active": True,
    },
    {
        "name_en": "Proteins",
        "name_ar": "البروتينات",
        "description": (
            "Chicken and other protein meal options."
        ),
        "image_url": None,
        "is_active": True,
    },
]


MEAL_DATA = [
    {
        "category": "Carbohydrates",
        "name_en": "Mashed Potatoes",
        "name_ar": "بطاطس مهروسة",
        "description_en": "Smooth and creamy mashed potatoes.",
        "description_ar": "بطاطس مهروسة ناعمة وكريمية.",
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 0.0,
        "price": 0.0,
        "image_url": None,
        "ingredients": [],
        "allergens": [],
        "diet_tags": [],
        "is_available": True,
    },
    {
        "category": "Carbohydrates",
        "name_en": "Creamy Pasta",
        "name_ar": "باستا كريمية",
        "description_en": "Pasta prepared with a smooth creamy sauce.",
        "description_ar": "باستا محضرة بصلصة كريمية ناعمة.",
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 0.0,
        "price": 0.0,
        "image_url": None,
        "ingredients": [],
        "allergens": [],
        "diet_tags": [],
        "is_available": True,
    },
    {
        "category": "Carbohydrates",
        "name_en": "White Rice",
        "name_ar": "أرز أبيض",
        "description_en": "Steamed white rice.",
        "description_ar": "أرز أبيض مطهو على البخار.",
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 0.0,
        "price": 0.0,
        "image_url": None,
        "ingredients": [],
        "allergens": [],
        "diet_tags": [],
        "is_available": True,
    },
    {
        "category": "Carbohydrates",
        "name_en": "Biryani Rice",
        "name_ar": "أرز برياني",
        "description_en": "Seasoned biryani-style rice.",
        "description_ar": "أرز متبل على طريقة البرياني.",
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 0.0,
        "price": 0.0,
        "image_url": None,
        "ingredients": [],
        "allergens": [],
        "diet_tags": [],
        "is_available": True,
    },
    {
        "category": "Proteins",
        "name_en": "Chicken Satay",
        "name_ar": "دجاج ساتيه",
        "description_en": "Seasoned chicken inspired by satay flavours.",
        "description_ar": "دجاج متبل بنكهات مستوحاة من الساتيه.",
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 0.0,
        "price": 0.0,
        "image_url": None,
        "ingredients": [],
        "allergens": [],
        "diet_tags": [],
        "is_available": True,
    },
    {
        "category": "Proteins",
        "name_en": "Mexican Chicken",
        "name_ar": "دجاج مكسيكي",
        "description_en": (
            "Chicken prepared with Mexican-inspired seasoning."
        ),
        "description_ar": "دجاج محضر بتوابل مستوحاة من المطبخ المكسيكي.",
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 0.0,
        "price": 0.0,
        "image_url": None,
        "ingredients": [],
        "allergens": [],
        "diet_tags": [],
        "is_available": True,
    },
    {
        "category": "Proteins",
        "name_en": "Creamy Chicken",
        "name_ar": "دجاج كريمي",
        "description_en": "Chicken served with a smooth creamy sauce.",
        "description_ar": "دجاج يقدم مع صلصة كريمية ناعمة.",
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 0.0,
        "price": 0.0,
        "image_url": None,
        "ingredients": [],
        "allergens": [],
        "diet_tags": [],
        "is_available": True,
    },
    {
        "category": "Proteins",
        "name_en": "Chicken Fajita",
        "name_ar": "فاهيتا الدجاج",
        "description_en": "Chicken prepared with fajita-style seasoning.",
        "description_ar": "دجاج محضر بتوابل الفاهيتا.",
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 0.0,
        "price": 0.0,
        "image_url": None,
        "ingredients": [],
        "allergens": [],
        "diet_tags": [],
        "is_available": True,
    },
    {
        "category": "Proteins",
        "name_en": "Lemon Chicken",
        "name_ar": "دجاج بالليمون",
        "description_en": "Chicken prepared with a fresh lemon flavour.",
        "description_ar": "دجاج محضر بنكهة الليمون الطازج.",
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 0.0,
        "price": 0.0,
        "image_url": None,
        "ingredients": [],
        "allergens": [],
        "diet_tags": [],
        "is_available": True,
    },
]


PLAN_DATA = [
    {
        "name": "1 Month Hot Plan",
        "description": (
            "One-month individual hot-meal subscription."
        ),
        "price": Decimal("1999.00"),
        "duration_days": 30,
        "meals_per_day": 1,
        "total_meals": 30,
        "delivery_type": DeliveryType.INDIVIDUAL,
        "delivery_temperature": DeliveryTemperature.HOT,
        "image_url": None,
        "is_active": True,
    },
    {
        "name": "1 Month Cold Plan",
        "description": (
            "One-month bulk cold-meal subscription."
        ),
        "price": Decimal("1799.00"),
        "duration_days": 30,
        "meals_per_day": 1,
        "total_meals": 30,
        "delivery_type": DeliveryType.BULK,
        "delivery_temperature": DeliveryTemperature.COLD,
        "image_url": None,
        "is_active": True,
    },
    {
        "name": "2 Months Hot Plan",
        "description": (
            "Two-month individual hot-meal subscription."
        ),
        "price": Decimal("3699.00"),
        "duration_days": 60,
        "meals_per_day": 1,
        "total_meals": 60,
        "delivery_type": DeliveryType.INDIVIDUAL,
        "delivery_temperature": DeliveryTemperature.HOT,
        "image_url": None,
        "is_active": True,
    },
    {
        "name": "2 Months Cold Plan",
        "description": (
            "Two-month bulk cold-meal subscription."
        ),
        "price": Decimal("3299.00"),
        "duration_days": 60,
        "meals_per_day": 1,
        "total_meals": 60,
        "delivery_type": DeliveryType.BULK,
        "delivery_temperature": DeliveryTemperature.COLD,
        "image_url": None,
        "is_active": True,
    },
    {
        "name": "3 Months Hot Plan",
        "description": (
            "Three-month individual hot-meal subscription."
        ),
        "price": Decimal("5099.00"),
        "duration_days": 90,
        "meals_per_day": 1,
        "total_meals": 90,
        "delivery_type": DeliveryType.INDIVIDUAL,
        "delivery_temperature": DeliveryTemperature.HOT,
        "image_url": None,
        "is_active": True,
    },
    {
        "name": "3 Months Cold Plan",
        "description": (
            "Three-month bulk cold-meal subscription."
        ),
        "price": Decimal("4499.00"),
        "duration_days": 90,
        "meals_per_day": 1,
        "total_meals": 90,
        "delivery_type": DeliveryType.BULK,
        "delivery_temperature": DeliveryTemperature.COLD,
        "image_url": None,
        "is_active": True,
    },
]


WEEKLY_MENU_DATA = {
    WeekDay.MONDAY: {
        "Carbohydrates": "White Rice",
        "Proteins": "Lemon Chicken",
    },
    WeekDay.TUESDAY: {
        "Carbohydrates": "Creamy Pasta",
        "Proteins": "Mexican Chicken",
    },
    WeekDay.WEDNESDAY: {
        "Carbohydrates": "Biryani Rice",
        "Proteins": "Chicken Satay",
    },
    WeekDay.THURSDAY: {
        "Carbohydrates": "Mashed Potatoes",
        "Proteins": "Chicken Fajita",
    },
    WeekDay.FRIDAY: {
        "Carbohydrates": "White Rice",
        "Proteins": "Creamy Chicken",
    },
    WeekDay.SATURDAY: {
        "Carbohydrates": "Creamy Pasta",
        "Proteins": "Lemon Chicken",
    },
    WeekDay.SUNDAY: {
        "Carbohydrates": "Biryani Rice",
        "Proteins": "Mexican Chicken",
    },
}


EnumType = TypeVar("EnumType")

def resolve_enum_member(
    enum_class: type[EnumType],
    candidates: list[str],
) -> EnumType:
    """
    Resolve an enum member using either its member name or value.

    This makes the seed compatible with enum definitions such as:

        GENERAL = "general"

    or:

        STANDARD = "standard"
    """
    normalized_candidates = {
        candidate.strip().lower()
        for candidate in candidates
    }

    for member in enum_class:
        member_name = str(getattr(member, "name", "")).lower()
        member_value = str(getattr(member, "value", "")).lower()

        if (
            member_name in normalized_candidates
            or member_value in normalized_candidates
        ):
            return member

    available_values = [
        f"{getattr(member, 'name', member)}="
        f"{getattr(member, 'value', member)}"
        for member in enum_class
    ]

    raise RuntimeError(
        f"Could not select a value from {enum_class.__name__}. "
        f"Tried: {candidates}. "
        f"Available values: {available_values}"
    )


def get_default_plan_type() -> PlanType:
    return resolve_enum_member(
        PlanType,
        [
            "subscription",
            "standard",
            "monthly",
            "regular",
            "meal_plan",
            "general",
        ],
    )


def get_default_plan_goal() -> PlanGoal:
    return resolve_enum_member(
        PlanGoal,
        [
            "general",
            "general_health",
            "healthy_lifestyle",
            "maintenance",
            "balanced",
            "wellness",
        ],
    )

def validate_seed_configuration() -> None:
    if len(SUPER_ADMIN_PASSWORD) < 8:
        raise RuntimeError(
            "SEED_SUPER_ADMIN_PASSWORD must contain "
            "at least 8 characters."
        )

    if len(ADMIN_PASSWORD) < 8:
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD must contain "
            "at least 8 characters."
        )

    if SUPER_ADMIN_EMAIL == ADMIN_EMAIL:
        raise RuntimeError(
            "Super Admin and Admin must use different "
            "email addresses."
        )

    if SUPER_ADMIN_PHONE == ADMIN_PHONE:
        raise RuntimeError(
            "Super Admin and Admin must use different "
            "phone numbers."
        )

    allowed_email_domains = (
        "@gmail.com",
        "@nutriomeals.com",
    )

    if not SUPER_ADMIN_EMAIL.endswith(allowed_email_domains):
        print(
            "Warning: Super Admin email uses an unexpected domain:",
            SUPER_ADMIN_EMAIL,
        )

    if not ADMIN_EMAIL.endswith(allowed_email_domains):
        print(
            "Warning: Admin email uses an unexpected domain:",
            ADMIN_EMAIL,
        )

def get_user_by_email(
    db: Session,
    email: str,
) -> User | None:
    normalized_email = email.strip().lower()

    return (
        db.query(User)
        .filter(
            func.lower(User.email) == normalized_email,
        )
        .first()
    )


def get_user_by_phone(
    db: Session,
    phone: str,
) -> User | None:
    normalized_phone = phone.strip()

    return (
        db.query(User)
        .filter(User.phone == normalized_phone)
        .first()
    )


def create_or_update_admin_user(
    db: Session,
    *,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    password: str,
    role: UserRole,
) -> tuple[User, bool]:
    normalized_email = email.strip().lower()
    normalized_phone = phone.strip()

    user = get_user_by_email(
        db=db,
        email=normalized_email,
    )

    phone_owner = get_user_by_phone(
        db=db,
        phone=normalized_phone,
    )

    if (
        phone_owner is not None
        and (
            user is None
            or phone_owner.id != user.id
        )
    ):
        raise RuntimeError(
            f"Phone number {normalized_phone} is already used "
            f"by another account: {phone_owner.email}"
        )

    created = user is None

    if created:
        user = User(
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=normalized_email,
            phone=normalized_phone,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
            is_verified=True,
            created_at=datetime.now(UTC),
        )

        db.add(user)

    else:
        user.first_name = first_name.strip()
        user.last_name = last_name.strip()
        user.phone = normalized_phone
        user.role = role
        user.is_active = True
        user.is_verified = True

        # Running the seed again resets the account password
        # to the value stored in .env.seed.
        user.hashed_password = hash_password(password)

    db.flush()

    return user, created

def get_category_by_name(
    db: Session,
    name_en: str,
) -> MealCategory | None:
    return (
        db.query(MealCategory)
        .filter(
            func.lower(MealCategory.name_en)
            == name_en.strip().lower(),
        )
        .first()
    )


def create_or_update_category(
    db: Session,
    data: dict[str, Any],
) -> tuple[MealCategory, bool]:
    category = get_category_by_name(
        db,
        data["name_en"],
    )

    created = category is None

    if created:
        category = MealCategory(
            name_en=data["name_en"],
            name_ar=data["name_ar"],
            description=data["description"],
            image_url=data["image_url"],
            is_active=data["is_active"],
        )

        db.add(category)

    else:
        category.name_ar = data["name_ar"]
        category.description = data["description"]
        category.is_active = data["is_active"]

        # Preserve an image uploaded through the admin panel.
        if not category.image_url and data["image_url"]:
            category.image_url = data["image_url"]

    db.flush()

    return category, created


def seed_categories(
    db: Session,
) -> tuple[dict[str, MealCategory], int, int]:
    categories: dict[str, MealCategory] = {}
    created_count = 0
    updated_count = 0

    for category_data in CATEGORY_DATA:
        category, created = create_or_update_category(
            db,
            category_data,
        )

        categories[category.name_en] = category

        if created:
            created_count += 1
        else:
            updated_count += 1

    return categories, created_count, updated_count

def get_meal_by_name(
    db: Session,
    name_en: str,
) -> Meal | None:
    return (
        db.query(Meal)
        .filter(
            func.lower(Meal.name_en)
            == name_en.strip().lower(),
        )
        .first()
    )


def create_or_update_meal(
    db: Session,
    *,
    data: dict[str, Any],
    category: MealCategory,
) -> tuple[Meal, bool]:
    meal = get_meal_by_name(
        db,
        data["name_en"],
    )

    created = meal is None

    if created:
        meal = Meal(
            category_id=category.id,
            name_en=data["name_en"].strip(),
            name_ar=data.get("name_ar"),
            description_en=data.get("description_en"),
            description_ar=data.get("description_ar"),
            calories=float(data["calories"]),
            protein_g=float(data["protein_g"]),
            carbs_g=float(data["carbs_g"]),
            fat_g=float(data["fat_g"]),
            fiber_g=(
                float(data["fiber_g"])
                if data.get("fiber_g") is not None
                else None
            ),
            sugar_g=(
                float(data["sugar_g"])
                if data.get("sugar_g") is not None
                else None
            ),
            sodium_mg=(
                float(data["sodium_mg"])
                if data.get("sodium_mg") is not None
                else None
            ),
            price=float(data["price"]),
            image_url=data.get("image_url"),
            ingredients=data.get("ingredients"),
            allergens=data.get("allergens"),
            diet_tags=data.get("diet_tags"),
            is_available=data.get("is_available", True),
        )

        db.add(meal)

    else:
        meal.category_id = category.id
        meal.name_en = data["name_en"].strip()
        meal.name_ar = data.get("name_ar")
        meal.description_en = data.get("description_en")
        meal.description_ar = data.get("description_ar")
        meal.calories = float(data["calories"])
        meal.protein_g = float(data["protein_g"])
        meal.carbs_g = float(data["carbs_g"])
        meal.fat_g = float(data["fat_g"])

        meal.fiber_g = (
            float(data["fiber_g"])
            if data.get("fiber_g") is not None
            else None
        )

        meal.sugar_g = (
            float(data["sugar_g"])
            if data.get("sugar_g") is not None
            else None
        )

        meal.sodium_mg = (
            float(data["sodium_mg"])
            if data.get("sodium_mg") is not None
            else None
        )

        meal.price = float(data["price"])
        meal.ingredients = data.get("ingredients")
        meal.allergens = data.get("allergens")
        meal.diet_tags = data.get("diet_tags")
        meal.is_available = data.get("is_available", True)

        # Preserve an image uploaded through the admin dashboard.
        if not meal.image_url and data.get("image_url"):
            meal.image_url = data["image_url"]

    db.flush()

    return meal, created


def seed_meals(
    db: Session,
    categories: dict[str, MealCategory],
) -> tuple[dict[str, Meal], int, int]:
    meals: dict[str, Meal] = {}
    created_count = 0
    updated_count = 0

    for meal_data in MEAL_DATA:
        category_name = meal_data["category"]

        category = categories.get(category_name)

        if category is None:
            raise RuntimeError(
                f"Meal category '{category_name}' was not found."
            )

        meal, created = create_or_update_meal(
            db,
            data=meal_data,
            category=category,
        )

        meals[meal.name_en] = meal

        if created:
            created_count += 1
        else:
            updated_count += 1

    return meals, created_count, updated_count

def get_plan_by_name(
    db: Session,
    name: str,
) -> MealPlan | None:
    return (
        db.query(MealPlan)
        .filter(
            func.lower(MealPlan.name)
            == name.strip().lower(),
        )
        .first()
    )


def create_or_update_plan(
    db: Session,
    *,
    data: dict[str, Any],
    plan_type: PlanType,
    plan_goal: PlanGoal,
) -> tuple[MealPlan, bool]:
    plan = get_plan_by_name(
        db,
        data["name"],
    )

    created = plan is None

    if created:
        plan = MealPlan(
            name=data["name"],
            description=data["description"],
            plan_type=plan_type,
            goal=plan_goal,
            price=data["price"],
            duration_days=data["duration_days"],
            meals_per_day=data["meals_per_day"],
            total_meals=data["total_meals"],
            delivery_type=data["delivery_type"],
            delivery_temperature=(
                data["delivery_temperature"]
            ),
            image_url=data["image_url"],
            is_active=data["is_active"],
        )

        db.add(plan)

    else:
        plan.description = data["description"]
        plan.plan_type = plan_type
        plan.goal = plan_goal
        plan.price = data["price"]
        plan.duration_days = data["duration_days"]
        plan.meals_per_day = data["meals_per_day"]
        plan.total_meals = data["total_meals"]
        plan.delivery_type = data["delivery_type"]
        plan.delivery_temperature = (
            data["delivery_temperature"]
        )
        plan.is_active = data["is_active"]

        # Preserve images uploaded through the admin panel.
        if not plan.image_url and data["image_url"]:
            plan.image_url = data["image_url"]

    db.flush()

    return plan, created


def seed_plans(
    db: Session,
) -> tuple[list[MealPlan], int, int]:
    plan_type = get_default_plan_type()
    plan_goal = get_default_plan_goal()

    plans: list[MealPlan] = []
    created_count = 0
    updated_count = 0

    for plan_data in PLAN_DATA:
        plan, created = create_or_update_plan(
            db,
            data=plan_data,
            plan_type=plan_type,
            plan_goal=plan_goal,
        )

        plans.append(plan)

        if created:
            created_count += 1
        else:
            updated_count += 1

    return plans, created_count, updated_count

def create_or_update_menu_item(
    db: Session,
    *,
    plan: MealPlan,
    meal: Meal,
    category: MealCategory,
    day_of_week: WeekDay,
    meal_time: MealTime,
    sort_order: int,
) -> tuple[PlanMenuItem, bool]:
    menu_item = (
        db.query(PlanMenuItem)
        .filter(
            PlanMenuItem.plan_id == plan.id,
            PlanMenuItem.day_of_week == day_of_week,
            PlanMenuItem.meal_time == meal_time,
            PlanMenuItem.category_id == category.id,
        )
        .first()
    )

    created = menu_item is None

    if created:
        menu_item = PlanMenuItem(
            plan_id=plan.id,
            meal_id=meal.id,
            category_id=category.id,
            day_of_week=day_of_week,
            meal_time=meal_time,
            quantity=1,
            sort_order=sort_order,
            is_active=True,
        )

        db.add(menu_item)

    else:
        menu_item.meal_id = meal.id
        menu_item.quantity = 1
        menu_item.sort_order = sort_order
        menu_item.is_active = True

    db.flush()

    return menu_item, created


def seed_weekly_menu(
    db: Session,
    *,
    plans: list[MealPlan],
    categories: dict[str, MealCategory],
    meals: dict[str, Meal],
) -> tuple[int, int]:
    created_count = 0
    updated_count = 0

    for plan in plans:
        for day_of_week, daily_menu in WEEKLY_MENU_DATA.items():
            for sort_order, category_name in enumerate(
                ["Carbohydrates", "Proteins"],
                start=1,
            ):
                meal_name = daily_menu[category_name]

                category = categories.get(category_name)
                meal = meals.get(meal_name)

                if category is None:
                    raise RuntimeError(
                        f"Category '{category_name}' was not found."
                    )

                if meal is None:
                    raise RuntimeError(
                        f"Meal '{meal_name}' was not found."
                    )

                menu_item, created = (
                    create_or_update_menu_item(
                        db,
                        plan=plan,
                        meal=meal,
                        category=category,
                        day_of_week=day_of_week,
                        meal_time=MealTime.LUNCH,
                        sort_order=sort_order,
                    )
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

    return created_count, updated_count

def seed_production_data() -> None:
    validate_seed_configuration()

    db = SessionLocal()

    try:

        super_admin, super_admin_created = (
            create_or_update_admin_user(
                db=db,
                first_name=SUPER_ADMIN_FIRST_NAME,
                last_name=SUPER_ADMIN_LAST_NAME,
                email=SUPER_ADMIN_EMAIL,
                phone=SUPER_ADMIN_PHONE,
                password=SUPER_ADMIN_PASSWORD,
                role=UserRole.SUPER_ADMIN,
            )
        )

        admin, admin_created = create_or_update_admin_user(
            db=db,
            first_name=ADMIN_FIRST_NAME,
            last_name=ADMIN_LAST_NAME,
            email=ADMIN_EMAIL,
            phone=ADMIN_PHONE,
            password=ADMIN_PASSWORD,
            role=UserRole.ADMIN,
        )

        (
            categories,
            categories_created,
            categories_updated,
        ) = seed_categories(db)

        (
            meals,
            meals_created,
            meals_updated,
        ) = seed_meals(
            db,
            categories,
        )
        
        
        (
            plans,
            plans_created,
            plans_updated,
        ) = seed_plans(db)

        (
            menu_items_created,
            menu_items_updated,
        ) = seed_weekly_menu(
            db,
            plans=plans,
            categories=categories,
            meals=meals,
        )

        db.commit()

        db.refresh(super_admin)
        db.refresh(admin)

        print()
        print("=" * 60)
        print("NutrioMeals production seed completed successfully")
        print("=" * 60)
        print()

        print(
            "Super Admin:",
            "created" if super_admin_created else "updated",
        )
        print(f"  ID: {super_admin.id}")
        print(
            f"  Name: "
            f"{super_admin.first_name} "
            f"{super_admin.last_name}"
        )
        print(f"  Email: {super_admin.email}")
        print(f"  Phone: {super_admin.phone}")
        print(f"  Role: {super_admin.role.value}")
        print()

        print(
            "Admin:",
            "created" if admin_created else "updated",
        )
        print(f"  ID: {admin.id}")
        print(
            f"  Name: "
            f"{admin.first_name} "
            f"{admin.last_name}"
        )
        print(f"  Email: {admin.email}")
        print(f"  Phone: {admin.phone}")
        print(f"  Role: {admin.role.value}")
        print()

        print("Meal categories:")
        print(f"  Created: {categories_created}")
        print(f"  Updated: {categories_updated}")
        print(f"  Total seeded: {len(categories)}")
        print()

        print("Meals:")
        print(f"  Created: {meals_created}")
        print(f"  Updated: {meals_updated}")
        print(f"  Total seeded: {len(meals)}")
        print()

        print("Subscription plans:")
        print(f"  Created: {plans_created}")
        print(f"  Updated: {plans_updated}")
        print(f"  Total seeded: {len(plans)}")
        print()

        print("Weekly menu items:")
        print(f"  Created: {menu_items_created}")
        print(f"  Updated: {menu_items_updated}")
        print(
            "  Expected total: "
            f"{len(plans) * 7 * 2}"
        )
        print()

        print(
            "No customers, subscriptions, payments, orders, "
            "deliveries or notifications were created."
        )
        print()

        print(
            "Important: nutritional values and individual meal "
            "prices are currently placeholders."
        )
        print(
            "Update them through the admin API when the client "
            "provides the confirmed values."
        )
        print()

    except Exception as exc:
        db.rollback()

        print()
        print("=" * 60)
        print("NutrioMeals production seed failed")
        print("=" * 60)
        print(f"Reason: {exc}")
        print()

        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_production_data()