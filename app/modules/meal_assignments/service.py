from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.meal_assignments.models import (
    MealAssignment,
    MealAssignmentItem,
)
from app.modules.meals.models import Meal, MealCategory
from app.modules.subscriptions.models import (
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.users.models import (
    User,
    UserCategoryDeliveryPreference,
    UserRole,
)


def enum_value(value: Any) -> Any:
    """
    Convert Python enum values into JSON-safe values.
    """

    if value is None:
        return None

    if hasattr(value, "value"):
        return value.value

    return value


def clean_optional_text(
    value: str | None,
) -> str | None:
    """
    Remove unnecessary whitespace from optional text fields.

    Empty text is stored as None.
    """

    if value is None:
        return None

    cleaned_value = value.strip()

    if not cleaned_value:
        return None

    return cleaned_value


def normalize_role(value: Any) -> str | None:
    """
    Convert a user role into a lowercase comparable value.
    """

    normalized_value = enum_value(value)

    if normalized_value is None:
        return None

    return str(normalized_value).strip().lower()


def get_assignment_by_id(
    db: Session,
    assignment_id: int,
) -> MealAssignment | None:
    """
    Return one meal assignment with all required relationships.
    """

    return (
        db.query(MealAssignment)
        .options(
            selectinload(MealAssignment.items).selectinload(
                MealAssignmentItem.meal
            ),
            selectinload(MealAssignment.category),
            selectinload(MealAssignment.customer),
            selectinload(MealAssignment.driver),
            selectinload(MealAssignment.assigned_by_user),
            selectinload(MealAssignment.subscription),
            selectinload(
                MealAssignment.delivery_preference
            ),
        )
        .filter(
            MealAssignment.id == assignment_id,
        )
        .first()
    )


def get_user_or_404(
    db: Session,
    user_id: int,
) -> User:
    """
    Return an active customer.
    """

    user = (
        db.query(User)
        .filter(
            User.id == user_id,
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    if getattr(user, "is_active", True) is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer account is inactive",
        )

    return user


def get_subscription_or_404(
    db: Session,
    subscription_id: int,
) -> Subscription:
    """
    Return a subscription or raise a 404 response.
    """

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id,
        )
        .first()
    )

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    return subscription


def validate_subscription_for_assignment(
    subscription: Subscription,
    user_id: int,
    delivery_date: date,
) -> None:
    """
    Confirm that the subscription can receive meals on the
    selected delivery date.
    """

    if subscription.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The selected subscription does not belong "
                "to this customer"
            ),
        )

    if subscription.status != SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The subscription is not active",
        )

    if subscription.payment_status != PaymentStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The subscription has not been paid",
        )

    if subscription.start_date is not None:
        subscription_start_date = (
            subscription.start_date.date()
            if hasattr(subscription.start_date, "date")
            else subscription.start_date
        )

        if delivery_date < subscription_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "The delivery date is before the "
                    "subscription start date"
                ),
            )

    if subscription.end_date is not None:
        subscription_end_date = (
            subscription.end_date.date()
            if hasattr(subscription.end_date, "date")
            else subscription.end_date
        )

        if delivery_date > subscription_end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "The delivery date is after the "
                    "subscription end date"
                ),
            )


def get_category_or_404(
    db: Session,
    category_id: int,
) -> MealCategory:
    """
    Return an active meal category.
    """

    category = (
        db.query(MealCategory)
        .filter(
            MealCategory.id == category_id,
        )
        .first()
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Meal category {category_id} was not found"
            ),
        )

    if getattr(category, "is_active", True) is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Meal category {category_id} is inactive"
            ),
        )

    return category


def get_meal_or_404(
    db: Session,
    meal_id: int,
) -> Meal:
    """
    Return an active and available meal.
    """

    meal = (
        db.query(Meal)
        .filter(
            Meal.id == meal_id,
        )
        .first()
    )

    if meal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal {meal_id} was not found",
        )

    if hasattr(meal, "is_available"):
        if meal.is_available is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Meal {meal_id} is unavailable",
            )

    if hasattr(meal, "is_active"):
        if meal.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Meal {meal_id} is inactive",
            )

    return meal


def validate_meal_matches_category(
    meal: Meal,
    category_id: int,
) -> None:
    """
    Ensure that a selected meal belongs to the selected
    meal category.
    """

    if meal.category_id != category_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Meal {meal.id} does not belong to "
                f"meal category {category_id}"
            ),
        )


def get_delivery_preference_or_404(
    db: Session,
    delivery_preference_id: int,
    user_id: int,
    meal_category_id: int,
) -> UserCategoryDeliveryPreference:
    """
    Validate the delivery preference selected by the admin.

    The preference must:

    - exist
    - belong to the customer
    - belong to the selected meal category
    - be active
    - contain a delivery address
    """

    preference = (
        db.query(UserCategoryDeliveryPreference)
        .filter(
            UserCategoryDeliveryPreference.id
            == delivery_preference_id,
        )
        .first()
    )

    if preference is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery preference not found",
        )

    if preference.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The selected delivery preference does not "
                "belong to this customer"
            ),
        )

    if (
        preference.meal_category_id
        != meal_category_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The selected delivery preference does not "
                "belong to the selected meal category"
            ),
        )

    if preference.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected delivery preference is inactive",
        )

    delivery_address = getattr(
        preference,
        "delivery_address",
        None,
    )

    if not delivery_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The selected delivery preference does not "
                "contain a delivery address"
            ),
        )

    return preference


def get_driver_or_404(
    db: Session,
    driver_id: int,
) -> User:
    """
    Validate the selected delivery driver.
    """

    driver = (
        db.query(User)
        .filter(
            User.id == driver_id,
        )
        .first()
    )

    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found",
        )

    if getattr(driver, "is_active", True) is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Driver account is inactive",
        )

    driver_role = normalize_role(
        getattr(driver, "role", None)
    )

    expected_role = normalize_role(
        UserRole.DRIVER
    )

    if driver_role != expected_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The selected user does not have the DRIVER role"
            ),
        )

    return driver


def validate_assignment_meals(
    db: Session,
    meal_category_id: int,
    meal_items: list[dict],
) -> list[tuple[Meal, dict]]:
    """
    Validate every meal included in one category assignment.

    Returns the validated meal objects together with their
    submitted item data.
    """

    if not meal_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "At least one meal must be selected for "
                "the meal category"
            ),
        )

    validated_items: list[tuple[Meal, dict]] = []
    submitted_meal_ids: set[int] = set()

    for item_data in meal_items:
        meal_id = item_data.get("meal_id")

        if meal_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Every meal item must contain meal_id",
            )

        if meal_id in submitted_meal_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Meal {meal_id} was submitted more than once"
                ),
            )

        submitted_meal_ids.add(meal_id)

        meal = get_meal_or_404(
            db=db,
            meal_id=meal_id,
        )

        validate_meal_matches_category(
            meal=meal,
            category_id=meal_category_id,
        )

        quantity = int(
            item_data.get("quantity") or 1
        )

        if quantity < 1 or quantity > 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Meal quantity must be between 1 and 20"
                ),
            )

        validated_items.append(
            (
                meal,
                {
                    "meal_id": meal_id,
                    "quantity": quantity,
                    "notes": clean_optional_text(
                        item_data.get("notes")
                    ),
                },
            )
        )

    return validated_items


def replace_assignment_items(
    db: Session,
    assignment: MealAssignment,
    validated_items: list[tuple[Meal, dict]],
) -> None:
    """
    Replace all meal items for an assignment.

    The assignment is treated as the current admin-selected
    menu for that category and delivery date.
    """

    existing_items = (
        db.query(MealAssignmentItem)
        .filter(
            MealAssignmentItem.meal_assignment_id
            == assignment.id,
        )
        .all()
    )

    for existing_item in existing_items:
        db.delete(existing_item)

    db.flush()

    for _, item_data in validated_items:
        assignment_item = MealAssignmentItem(
            meal_assignment_id=assignment.id,
            meal_id=item_data["meal_id"],
            quantity=item_data["quantity"],
            notes=item_data["notes"],
        )

        db.add(assignment_item)

    db.flush()


def create_assignment_items(
    db: Session,
    assignment: MealAssignment,
    validated_items: list[tuple[Meal, dict]],
) -> None:
    """
    Create meal items for a newly inserted assignment.
    """

    for _, item_data in validated_items:
        assignment_item = MealAssignmentItem(
            meal_assignment_id=assignment.id,
            meal_id=item_data["meal_id"],
            quantity=item_data["quantity"],
            notes=item_data["notes"],
        )

        db.add(assignment_item)

    db.flush()


def create_or_update_assignments(
    db: Session,
    user_id: int,
    subscription_id: int,
    delivery_date: date,
    assignment_items: list[dict],
    assigned_by: int,
) -> tuple[list[MealAssignment], int, int]:
    """
    Create or update meal-category assignments.

    One submitted assignment represents one meal category.

    Existing records are identified by:

        subscription_id
        delivery_date
        meal_category_id

    If one already exists, its driver, delivery preference,
    delivery time, notes and meal items are replaced.
    """

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

    if not assignment_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one meal category is required",
        )

    submitted_category_ids: set[int] = set()

    created_count = 0
    updated_count = 0

    saved_assignment_ids: list[int] = []

    try:
        for assignment_data in assignment_items:
            meal_category_id = assignment_data.get(
                "meal_category_id"
            )

            delivery_preference_id = assignment_data.get(
                "delivery_preference_id"
            )

            driver_id = assignment_data.get(
                "driver_id"
            )

            delivery_time = assignment_data.get(
                "delivery_time"
            )

            meal_items = assignment_data.get(
                "meals"
            ) or []

            if meal_category_id is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        "Every assignment must contain "
                        "meal_category_id"
                    ),
                )

            if meal_category_id in submitted_category_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "The same meal category cannot be "
                        "submitted more than once"
                    ),
                )

            submitted_category_ids.add(
                meal_category_id
            )

            if delivery_preference_id is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        "Every assignment must contain "
                        "delivery_preference_id"
                    ),
                )

            if driver_id is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        "Every assignment must contain driver_id"
                    ),
                )

            if delivery_time is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        "Every assignment must contain "
                        "delivery_time"
                    ),
                )

            get_category_or_404(
                db=db,
                category_id=meal_category_id,
            )

            get_delivery_preference_or_404(
                db=db,
                delivery_preference_id=(
                    delivery_preference_id
                ),
                user_id=user_id,
                meal_category_id=meal_category_id,
            )

            get_driver_or_404(
                db=db,
                driver_id=driver_id,
            )

            validated_meals = validate_assignment_meals(
                db=db,
                meal_category_id=meal_category_id,
                meal_items=meal_items,
            )

            existing_assignment = (
                db.query(MealAssignment)
                .filter(
                    MealAssignment.subscription_id
                    == subscription_id,
                    MealAssignment.delivery_date
                    == delivery_date,
                    MealAssignment.meal_category_id
                    == meal_category_id,
                )
                .first()
            )

            if existing_assignment is not None:
                existing_assignment.user_id = user_id

                existing_assignment.delivery_preference_id = (
                    delivery_preference_id
                )

                existing_assignment.driver_id = driver_id

                existing_assignment.delivery_time = (
                    delivery_time
                )

                existing_assignment.notes = (
                    clean_optional_text(
                        assignment_data.get("notes")
                    )
                )

                existing_assignment.assigned_by = (
                    assigned_by
                )

                existing_assignment.is_active = True

                db.flush()

                replace_assignment_items(
                    db=db,
                    assignment=existing_assignment,
                    validated_items=validated_meals,
                )

                saved_assignment_ids.append(
                    existing_assignment.id
                )

                updated_count += 1

            else:
                assignment = MealAssignment(
                    user_id=user_id,
                    subscription_id=subscription_id,
                    meal_category_id=meal_category_id,
                    delivery_preference_id=(
                        delivery_preference_id
                    ),
                    driver_id=driver_id,
                    delivery_date=delivery_date,
                    delivery_time=delivery_time,
                    notes=clean_optional_text(
                        assignment_data.get("notes")
                    ),
                    assigned_by=assigned_by,
                    is_active=True,
                )

                db.add(assignment)
                db.flush()

                create_assignment_items(
                    db=db,
                    assignment=assignment,
                    validated_items=validated_meals,
                )

                saved_assignment_ids.append(
                    assignment.id
                )

                created_count += 1

        db.commit()

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A meal assignment already exists for one "
                "of the submitted categories and dates"
            ),
        ) from exc

    except Exception:
        db.rollback()
        raise

    saved_assignments = (
        db.query(MealAssignment)
        .options(
            selectinload(MealAssignment.items).selectinload(
                MealAssignmentItem.meal
            ),
            selectinload(MealAssignment.category),
            selectinload(MealAssignment.customer),
            selectinload(MealAssignment.driver),
            selectinload(MealAssignment.assigned_by_user),
            selectinload(MealAssignment.subscription),
            selectinload(
                MealAssignment.delivery_preference
            ),
        )
        .filter(
            MealAssignment.id.in_(
                saved_assignment_ids
            ),
        )
        .order_by(
            MealAssignment.meal_category_id.asc(),
        )
        .all()
    )

    return (
        saved_assignments,
        created_count,
        updated_count,
    )


def update_assignment_meals(
    db: Session,
    assignment: MealAssignment,
    meal_items: list[dict],
) -> MealAssignment:
    """
    Replace the selected meals under one assignment.
    """

    validated_items = validate_assignment_meals(
        db=db,
        meal_category_id=assignment.meal_category_id,
        meal_items=meal_items,
    )

    try:
        replace_assignment_items(
            db=db,
            assignment=assignment,
            validated_items=validated_items,
        )

        db.commit()

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The same meal cannot be added more than once "
                "to an assignment"
            ),
        ) from exc

    except Exception:
        db.rollback()
        raise

    refreshed_assignment = get_assignment_by_id(
        db=db,
        assignment_id=assignment.id,
    )

    if refreshed_assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal assignment not found after update",
        )

    return refreshed_assignment


def serialize_meal(
    meal: Meal | None,
) -> dict | None:
    """
    Convert a meal model into the nested API structure.
    """

    if meal is None:
        return None

    return {
        "id": meal.id,
        "category_id": meal.category_id,
        "name_en": meal.name_en,
        "name_ar": getattr(
            meal,
            "name_ar",
            None,
        ),
        "description_en": getattr(
            meal,
            "description_en",
            None,
        ),
        "description_ar": getattr(
            meal,
            "description_ar",
            None,
        ),
        "calories": meal.calories,
        "protein_g": meal.protein_g,
        "carbs_g": meal.carbs_g,
        "fat_g": meal.fat_g,
        "fiber_g": getattr(
            meal,
            "fiber_g",
            None,
        ),
        "sugar_g": getattr(
            meal,
            "sugar_g",
            None,
        ),
        "sodium_mg": getattr(
            meal,
            "sodium_mg",
            None,
        ),
        "price": meal.price,
        "image_url": getattr(
            meal,
            "image_url",
            None,
        ),
        "ingredients": (
            getattr(meal, "ingredients", None) or []
        ),
        "allergens": (
            getattr(meal, "allergens", None) or []
        ),
        "diet_tags": (
            getattr(meal, "diet_tags", None) or []
        ),
    }


def serialize_delivery_preference(
    preference: UserCategoryDeliveryPreference | None,
) -> dict | None:
    """
    Convert a delivery preference into the nested API structure.
    """

    if preference is None:
        return None

    return {
        "id": preference.id,
        "user_id": preference.user_id,
        "meal_category_id": (
            preference.meal_category_id
        ),
        "place_type": enum_value(
            getattr(
                preference,
                "place_type",
                None,
            )
        ),
        "place_name": getattr(
            preference,
            "place_name",
            None,
        ),
        "city": getattr(
            preference,
            "city",
            None,
        ),
        "delivery_area": getattr(
            preference,
            "delivery_area",
            None,
        ),
        "delivery_address": getattr(
            preference,
            "delivery_address",
            None,
        ),
        "latitude": getattr(
            preference,
            "latitude",
            None,
        ),
        "longitude": getattr(
            preference,
            "longitude",
            None,
        ),
        "preferred_delivery_time": getattr(
            preference,
            "preferred_delivery_time",
            None,
        ),
        "delivery_note": getattr(
            preference,
            "delivery_note",
            None,
        ),
        "is_active": preference.is_active,
    }


def build_assignment_response(
    db: Session,
    assignment: MealAssignment,
) -> dict:
    """
    Build the complete MealAssignmentResponse structure.
    """

    loaded_assignment = get_assignment_by_id(
        db=db,
        assignment_id=assignment.id,
    )

    if loaded_assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal assignment not found",
        )

    category = loaded_assignment.category
    customer = loaded_assignment.customer
    driver = loaded_assignment.driver

    assigned_by_user = (
        loaded_assignment.assigned_by_user
    )

    subscription = loaded_assignment.subscription

    preference = (
        loaded_assignment.delivery_preference
    )

    meal_items = []

    for assignment_item in loaded_assignment.items:
        meal_items.append(
            {
                "id": assignment_item.id,
                "meal_assignment_id": (
                    assignment_item.meal_assignment_id
                ),
                "meal_id": assignment_item.meal_id,
                "quantity": assignment_item.quantity,
                "notes": assignment_item.notes,
                "created_at": assignment_item.created_at,
                "updated_at": assignment_item.updated_at,
                "meal": serialize_meal(
                    assignment_item.meal
                ),
            }
        )

    return {
        "id": loaded_assignment.id,
        "user_id": loaded_assignment.user_id,
        "subscription_id": (
            loaded_assignment.subscription_id
        ),
        "meal_category_id": (
            loaded_assignment.meal_category_id
        ),
        "delivery_preference_id": (
            loaded_assignment.delivery_preference_id
        ),
        "driver_id": loaded_assignment.driver_id,
        "delivery_date": (
            loaded_assignment.delivery_date
        ),
        "delivery_time": (
            loaded_assignment.delivery_time
        ),
        "notes": loaded_assignment.notes,
        "assigned_by": loaded_assignment.assigned_by,
        "is_active": loaded_assignment.is_active,
        "assigned_at": loaded_assignment.assigned_at,
        "updated_at": loaded_assignment.updated_at,
        "category": (
            {
                "id": category.id,
                "name_en": category.name_en,
                "name_ar": getattr(
                    category,
                    "name_ar",
                    None,
                ),
                "image_url": getattr(
                    category,
                    "image_url",
                    None,
                ),
            }
            if category is not None
            else None
        ),
        "meals": meal_items,
        "customer": (
            {
                "id": customer.id,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "email": customer.email,
                "phone": getattr(
                    customer,
                    "phone",
                    None,
                ),
                "allergies": (
                    getattr(
                        customer,
                        "allergies",
                        None,
                    )
                    or []
                ),
                "dietary_preference": enum_value(
                    getattr(
                        customer,
                        "dietary_preference",
                        None,
                    )
                ),
                "fitness_goal": enum_value(
                    getattr(
                        customer,
                        "fitness_goal",
                        None,
                    )
                ),
            }
            if customer is not None
            else None
        ),
        "driver": (
            {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "email": driver.email,
                "phone": getattr(
                    driver,
                    "phone",
                    None,
                ),
                "role": enum_value(
                    getattr(
                        driver,
                        "role",
                        None,
                    )
                ),
                "is_active": getattr(
                    driver,
                    "is_active",
                    True,
                ),
            }
            if driver is not None
            else None
        ),
        "assigned_by_user": (
            {
                "id": assigned_by_user.id,
                "first_name": (
                    assigned_by_user.first_name
                ),
                "last_name": (
                    assigned_by_user.last_name
                ),
                "role": enum_value(
                    getattr(
                        assigned_by_user,
                        "role",
                        None,
                    )
                ),
            }
            if assigned_by_user is not None
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
            if subscription is not None
            else None
        ),
        "delivery_preference": (
            serialize_delivery_preference(
                preference
            )
        ),
    }