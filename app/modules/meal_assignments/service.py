from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.meal_assignments.models import MealAssignment
from app.modules.meals.models import Meal, MealCategory
from app.modules.subscriptions.models import (
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.users.models import User


def enum_value(value):
    if value is None:
        return None

    if hasattr(value, "value"):
        return value.value

    return str(value)


def clean_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    cleaned_value = value.strip()

    if not cleaned_value:
        return None

    return cleaned_value


def get_assignment_by_id(
    db: Session,
    assignment_id: int,
) -> MealAssignment | None:
    return (
        db.query(MealAssignment)
        .filter(
            MealAssignment.id == assignment_id
        )
        .first()
    )


def get_user_or_404(
    db: Session,
    user_id: int,
) -> User:
    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    if user.is_active is False:
        raise HTTPException(
            status_code=400,
            detail="Customer account is inactive",
        )

    return user


def get_subscription_or_404(
    db: Session,
    subscription_id: int,
) -> Subscription:
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id
        )
        .first()
    )

    if subscription is None:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    return subscription


def validate_subscription_for_assignment(
    subscription: Subscription,
    user_id: int,
    delivery_date: date,
) -> None:
    if subscription.user_id != user_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "The selected subscription does not "
                "belong to this customer"
            ),
        )

    if subscription.status != SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail="The subscription is not active",
        )

    if subscription.payment_status != PaymentStatus.PAID:
        raise HTTPException(
            status_code=400,
            detail="The subscription has not been paid",
        )

    if subscription.start_date:
        if subscription.start_date.date() > delivery_date:
            raise HTTPException(
                status_code=400,
                detail=(
                    "The delivery date is before the "
                    "subscription start date"
                ),
            )

    if subscription.end_date:
        if subscription.end_date.date() < delivery_date:
            raise HTTPException(
                status_code=400,
                detail=(
                    "The delivery date is after the "
                    "subscription end date"
                ),
            )


def get_category_or_404(
    db: Session,
    category_id: int,
) -> MealCategory:
    category = (
        db.query(MealCategory)
        .filter(
            MealCategory.id == category_id
        )
        .first()
    )

    if category is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Meal category {category_id} "
                "was not found"
            ),
        )

    if category.is_active is False:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Meal category {category_id} "
                "is inactive"
            ),
        )

    return category


def get_meal_or_404(
    db: Session,
    meal_id: int,
) -> Meal:
    meal = (
        db.query(Meal)
        .filter(
            Meal.id == meal_id
        )
        .first()
    )

    if meal is None:
        raise HTTPException(
            status_code=404,
            detail=f"Meal {meal_id} was not found",
        )

    if meal.is_available is False:
        raise HTTPException(
            status_code=400,
            detail=f"Meal {meal_id} is unavailable",
        )

    return meal


def validate_meal_matches_category(
    meal: Meal,
    category_id: int,
) -> None:
    if meal.category_id != category_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Meal {meal.id} does not belong to "
                f"meal category {category_id}"
            ),
        )


def build_assignment_response(
    db: Session,
    assignment: MealAssignment,
) -> dict:
    category = (
        db.query(MealCategory)
        .filter(
            MealCategory.id
            == assignment.meal_category_id
        )
        .first()
    )

    meal = (
        db.query(Meal)
        .filter(
            Meal.id == assignment.meal_id
        )
        .first()
    )

    customer = (
        db.query(User)
        .filter(
            User.id == assignment.user_id
        )
        .first()
    )

    assigned_by_user = (
        db.query(User)
        .filter(
            User.id == assignment.assigned_by
        )
        .first()
    )

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id
            == assignment.subscription_id
        )
        .first()
    )

    return {
        "id": assignment.id,
        "user_id": assignment.user_id,
        "subscription_id": assignment.subscription_id,
        "meal_category_id": assignment.meal_category_id,
        "meal_id": assignment.meal_id,
        "delivery_date": assignment.delivery_date,
        "quantity": assignment.quantity,
        "notes": assignment.notes,
        "assigned_by": assignment.assigned_by,
        "is_active": assignment.is_active,
        "assigned_at": assignment.assigned_at,
        "updated_at": assignment.updated_at,
        "category": (
            {
                "id": category.id,
                "name_en": category.name_en,
                "name_ar": category.name_ar,
                "image_url": category.image_url,
            }
            if category
            else None
        ),
        "meal": (
            {
                "id": meal.id,
                "category_id": meal.category_id,
                "name_en": meal.name_en,
                "name_ar": meal.name_ar,
                "description_en": meal.description_en,
                "description_ar": meal.description_ar,
                "calories": meal.calories,
                "protein_g": meal.protein_g,
                "carbs_g": meal.carbs_g,
                "fat_g": meal.fat_g,
                "fiber_g": meal.fiber_g,
                "sugar_g": meal.sugar_g,
                "sodium_mg": meal.sodium_mg,
                "price": meal.price,
                "image_url": meal.image_url,
                "ingredients": meal.ingredients or [],
                "allergens": meal.allergens or [],
                "diet_tags": meal.diet_tags or [],
            }
            if meal
            else None
        ),
        "customer": (
            {
                "id": customer.id,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "email": customer.email,
                "phone": customer.phone,
                "allergies": customer.allergies or [],
                "dietary_preference": (
                    customer.dietary_preference
                ),
                "fitness_goal": enum_value(
                    customer.fitness_goal
                ),
            }
            if customer
            else None
        ),
        "assigned_by_user": (
            {
                "id": assigned_by_user.id,
                "first_name": assigned_by_user.first_name,
                "last_name": assigned_by_user.last_name,
                "role": enum_value(
                    assigned_by_user.role
                ),
            }
            if assigned_by_user
            else None
        ),
        "subscription": (
            {
                "id": subscription.id,
                "plan_id": subscription.plan_id,
                "status": enum_value(
                    subscription.status
                ),
                "payment_status": enum_value(
                    subscription.payment_status
                ),
                "start_date": subscription.start_date,
                "end_date": subscription.end_date,
            }
            if subscription
            else None
        ),
    }


def create_or_update_assignments(
    db: Session,
    user_id: int,
    subscription_id: int,
    delivery_date: date,
    assignment_items: list[dict],
    assigned_by: int,
) -> tuple[list[MealAssignment], int, int]:
    get_user_or_404(
        db=db,
        user_id=user_id,
    )

    subscription = get_subscription_or_404(
        db=db,
        subscription_id=subscription_id,
    )

    validate_subscription_for_assignment(
        subscription=subscription,
        user_id=user_id,
        delivery_date=delivery_date,
    )

    created_count = 0
    updated_count = 0
    saved_assignments = []

    for item in assignment_items:
        category_id = item["meal_category_id"]
        meal_id = item["meal_id"]

        get_category_or_404(
            db=db,
            category_id=category_id,
        )

        meal = get_meal_or_404(
            db=db,
            meal_id=meal_id,
        )

        validate_meal_matches_category(
            meal=meal,
            category_id=category_id,
        )

        existing_assignment = (
            db.query(MealAssignment)
            .filter(
                MealAssignment.subscription_id
                == subscription_id,
                MealAssignment.delivery_date
                == delivery_date,
                MealAssignment.meal_category_id
                == category_id,
            )
            .first()
        )

        if existing_assignment:
            existing_assignment.user_id = user_id
            existing_assignment.meal_id = meal_id
            existing_assignment.quantity = item.get(
                "quantity",
                1,
            )
            existing_assignment.notes = clean_optional_text(
                item.get("notes")
            )
            existing_assignment.assigned_by = assigned_by
            existing_assignment.is_active = True

            saved_assignments.append(
                existing_assignment
            )

            updated_count += 1

        else:
            assignment = MealAssignment(
                user_id=user_id,
                subscription_id=subscription_id,
                meal_category_id=category_id,
                meal_id=meal_id,
                delivery_date=delivery_date,
                quantity=item.get(
                    "quantity",
                    1,
                ),
                notes=clean_optional_text(
                    item.get("notes")
                ),
                assigned_by=assigned_by,
                is_active=True,
            )

            db.add(assignment)

            saved_assignments.append(
                assignment
            )

            created_count += 1

    db.commit()

    for assignment in saved_assignments:
        db.refresh(assignment)

    return (
        saved_assignments,
        created_count,
        updated_count,
    )