from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
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

from app.modules.deliveries.models import Delivery
from app.modules.orders.models import Order
STANDARD_CATEGORY_KEYS = {
    "breakfast",
    "lunch",
    "dinner",
    "snack",
}

ALLOWED_PREPARATION_UNITS = {
    "kg",
    "g",
    "litre",
    "ml",
    "whole",
    "half",
    "quarter",
    "piece",
    "portion",
    "tray",
    "pack",
}


def _enum_value(value: Any) -> Any:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else value


def _date_only(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _full_name(user: Any) -> str | None:
    if user is None:
        return None

    first_name = getattr(user, "first_name", None) or ""
    last_name = getattr(user, "last_name", None) or ""
    value = f"{first_name} {last_name}".strip()
    return value or None


def _category_key(category: Any) -> str:
    raw_name = (
        getattr(category, "name_en", None)
        or getattr(category, "name", None)
        or f"category_{getattr(category, 'id', 'unknown')}"
    )

    normalized = re.sub(
        r"[^a-z0-9]+",
        "_",
        str(raw_name).strip().lower(),
    ).strip("_")

    aliases = {
        "break_fast": "breakfast",
        "morning_meal": "breakfast",
        "midday_meal": "lunch",
        "evening_meal": "dinner",
        "snacks": "snack",
    }

    return aliases.get(normalized, normalized)


def _meal_summary(item: MealAssignmentItem) -> dict[str, Any]:
    meal = item.meal

    if meal is None:
        return {
            "id": item.meal_id,
            "name_en": "Unavailable meal",
            "quantity": item.quantity,
            "preparation_quantity": item.preparation_quantity,
            "preparation_unit": item.preparation_unit,
            "item_notes": item.notes,
        }

    return {
        "id": meal.id,
        "name_en": getattr(meal, "name_en", None)
        or getattr(meal, "name", "Meal"),
        "name_ar": getattr(meal, "name_ar", None),
        "description_en": getattr(meal, "description_en", None)
        or getattr(meal, "description", None),
        "description_ar": getattr(meal, "description_ar", None),
        "calories": getattr(meal, "calories", None),
        "protein_g": getattr(
            meal,
            "protein_g",
            getattr(meal, "protein", None),
        ),
        "carbs_g": getattr(
            meal,
            "carbs_g",
            getattr(meal, "carbs", None),
        ),
        "fat_g": getattr(
            meal,
            "fat_g",
            getattr(meal, "fat", None),
        ),
        "fiber_g": getattr(meal, "fiber_g", None),
        "sugar_g": getattr(meal, "sugar_g", None),
        "sodium_mg": getattr(meal, "sodium_mg", None),
        "quantity": item.quantity,
        "preparation_quantity": item.preparation_quantity,
        "preparation_unit": item.preparation_unit,
        "item_notes": item.notes,
        "ingredients": getattr(meal, "ingredients", None) or [],
        "allergens": getattr(meal, "allergens", None) or [],
        "diet_tags": getattr(meal, "diet_tags", None) or [],
        "image_url": getattr(meal, "image_url", None),
    }


def _driver_summary(driver: Any) -> dict[str, Any] | None:
    if driver is None:
        return None

    return {
        "id": driver.id,
        "first_name": getattr(driver, "first_name", None),
        "last_name": getattr(driver, "last_name", None),
        "full_name": _full_name(driver),
        "phone": getattr(driver, "phone", None),
    }


def _preference_summary(preference: Any) -> dict[str, Any] | None:
    if preference is None:
        return None

    return {
        "id": preference.id,
        "place_type": _enum_value(
            getattr(preference, "place_type", None)
        ),
        "place_name": getattr(preference, "place_name", None),
        "city": getattr(preference, "city", None),
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
    }


def _order_summary(order: Order | None) -> dict[str, Any] | None:
    if order is None:
        return None

    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": _enum_value(order.status),
        "total_amount": float(order.total_amount or 0),
        "created_at": order.created_at,
    }


def _delivery_summary(
    delivery: Delivery | None,
) -> dict[str, Any] | None:
    if delivery is None:
        return None

    return {
        "id": delivery.id,
        "status": _enum_value(delivery.status),
        "ready_for_pickup_at": delivery.ready_for_pickup_at,
        "picked_up_at": delivery.picked_up_at,
        "out_for_delivery_at": delivery.out_for_delivery_at,
        "delivered_at": delivery.delivered_at,
        "failed_at": delivery.failed_at,
        "failure_reason": delivery.failure_reason,
    }


def _load_assignments(
    db: Session,
    *,
    user_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    subscription_id: int | None = None,
) -> list[MealAssignment]:
    query = (
        db.query(MealAssignment)
        .options(
            selectinload(MealAssignment.items).selectinload(
                MealAssignmentItem.meal
            ),
            selectinload(MealAssignment.category),
            selectinload(MealAssignment.driver),
            selectinload(MealAssignment.delivery_preference),
            selectinload(MealAssignment.subscription),
        )
        .filter(
            MealAssignment.user_id == user_id,
            MealAssignment.is_active.is_(True),
        )
    )

    if start_date is not None:
        query = query.filter(
            MealAssignment.delivery_date >= start_date
        )

    if end_date is not None:
        query = query.filter(
            MealAssignment.delivery_date <= end_date
        )

    if subscription_id is not None:
        query = query.filter(
            MealAssignment.subscription_id == subscription_id
        )

    return (
        query.order_by(
            MealAssignment.delivery_date.asc(),
            MealAssignment.delivery_time.asc(),
            MealAssignment.meal_category_id.asc(),
        )
        .all()
    )


def _load_order_maps(
    db: Session,
    assignments: list[MealAssignment],
) -> tuple[dict[int, Order], dict[int, Delivery]]:
    assignment_ids = [assignment.id for assignment in assignments]

    if not assignment_ids:
        return {}, {}

    orders = (
        db.query(Order)
        .options(selectinload(Order.delivery))
        .filter(Order.meal_assignment_id.in_(assignment_ids))
        .all()
    )

    order_by_assignment = {
        order.meal_assignment_id: order
        for order in orders
    }

    delivery_by_order = {
        order.id: order.delivery
        for order in orders
        if order.delivery is not None
    }

    return order_by_assignment, delivery_by_order


def _subscription_start_date(
    assignment: MealAssignment,
) -> date | None:
    subscription = assignment.subscription

    if subscription is None:
        return None

    return _date_only(getattr(subscription, "start_date", None))


def _serialize_assignment(
    assignment: MealAssignment,
    *,
    order: Order | None,
    delivery: Delivery | None,
) -> dict[str, Any]:
    category = assignment.category
    key = _category_key(category)

    return {
        "assignment_id": assignment.id,
        "category_id": assignment.meal_category_id,
        "category_key": key,
        "category_name_en": (
            getattr(category, "name_en", None)
            or getattr(category, "name", key.replace("_", " ").title())
        ),
        "category_name_ar": getattr(category, "name_ar", None),
        "delivery_date": assignment.delivery_date,
        "delivery_time": assignment.delivery_time,
        "assignment_notes": assignment.notes,
        "meals": [
            _meal_summary(item)
            for item in assignment.items
        ],
        "driver": _driver_summary(assignment.driver),
        "delivery_preference": _preference_summary(
            assignment.delivery_preference
        ),
        "order": _order_summary(order),
        "delivery": _delivery_summary(delivery),
    }


def build_customer_schedule(
    db: Session,
    *,
    user_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    subscription_id: int | None = None,
) -> dict[str, Any]:
    if (
        start_date is not None
        and end_date is not None
        and start_date > end_date
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date cannot be after end_date",
        )

    assignments = _load_assignments(
        db=db,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        subscription_id=subscription_id,
    )

    order_map, delivery_map = _load_order_maps(
        db=db,
        assignments=assignments,
    )

    grouped: dict[date, list[MealAssignment]] = defaultdict(list)

    for assignment in assignments:
        grouped[assignment.delivery_date].append(assignment)

    days: list[dict[str, Any]] = []

    for delivery_date in sorted(grouped):
        date_assignments = grouped[delivery_date]

        day_payload: dict[str, Any] = {
            "day_number": None,
            "delivery_date": delivery_date,
            "breakfast": None,
            "lunch": None,
            "dinner": None,
            "snack": None,
            "other_categories": {},
        }

        start = _subscription_start_date(date_assignments[0])
        if start is not None:
            day_payload["day_number"] = (
                delivery_date - start
            ).days + 1

        for assignment in date_assignments:
            order = order_map.get(assignment.id)
            delivery = (
                delivery_map.get(order.id)
                if order is not None
                else None
            )

            serialized = _serialize_assignment(
                assignment,
                order=order,
                delivery=delivery,
            )

            key = serialized["category_key"]

            if key in STANDARD_CATEGORY_KEYS:
                day_payload[key] = serialized
            else:
                day_payload["other_categories"][key] = serialized

        days.append(day_payload)

    actual_start = days[0]["delivery_date"] if days else start_date
    actual_end = days[-1]["delivery_date"] if days else end_date

    return {
        "success": True,
        "message": "Your assigned meal schedule was retrieved successfully.",
        "total_days": len(days),
        "total_assignments": len(assignments),
        "start_date": actual_start,
        "end_date": actual_end,
        "days": days,
    }


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

    quantity:
        Number of portions/packages.

    preparation_quantity and preparation_unit:
        Actual amount assigned to the customer, such as
        2 kg, 500 g, 0.5 whole, or 1 portion.
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

        meal_id = int(meal_id)

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

        quantity = int(item_data.get("quantity") or 1)

        if quantity < 1 or quantity > 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Meal quantity must be between 1 and 20",
            )

        raw_preparation_quantity = item_data.get(
            "preparation_quantity",
            1,
        )

        try:
            preparation_quantity = Decimal(
                str(raw_preparation_quantity)
            )
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Meal {meal_id} has an invalid "
                    "preparation_quantity"
                ),
            ) from exc

        if preparation_quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Preparation quantity must be greater than zero"
                ),
            )

        if preparation_quantity.as_tuple().exponent < -3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Preparation quantity cannot contain more than "
                    "3 decimal places"
                ),
            )

        if preparation_quantity >= Decimal("10000000"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Preparation quantity is too large",
            )

        preparation_unit = str(
            item_data.get("preparation_unit") or "portion"
        ).strip().lower()

        if preparation_unit not in ALLOWED_PREPARATION_UNITS:
            allowed_units = ", ".join(
                sorted(ALLOWED_PREPARATION_UNITS)
            )

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unsupported preparation unit "
                    f"'{preparation_unit}'. Allowed units: "
                    f"{allowed_units}"
                ),
            )

        validated_items.append(
            (
                meal,
                {
                    "meal_id": meal_id,
                    "quantity": quantity,
                    "preparation_quantity": preparation_quantity,
                    "preparation_unit": preparation_unit,
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
            preparation_quantity=item_data[
                "preparation_quantity"
            ],
            preparation_unit=item_data["preparation_unit"],
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
            preparation_quantity=item_data[
                "preparation_quantity"
            ],
            preparation_unit=item_data["preparation_unit"],
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
                "preparation_quantity": (
                    assignment_item.preparation_quantity
                ),
                "preparation_unit": (
                    assignment_item.preparation_unit
                ),
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