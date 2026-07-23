from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.meal_assignments.models import MealAssignment
from app.modules.meals.models import Meal, MealCategory
from app.modules.orders.models import (
    Order,
    OrderSource,
    OrderStatus,
)
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import (
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.users.models import (
    User,
    UserCategoryDeliveryPreference,
)


def enum_value(value):
    """
    Convert a Python enum or SQLAlchemy enum to a plain value.
    """

    if value is None:
        return None

    if hasattr(value, "value"):
        return value.value

    return str(value)


def normalize_service_datetime(
    target_date: date,
) -> datetime:
    """
    Store the order delivery date at midnight.

    This keeps duplicate checks predictable because the
    orders table uses DateTime for delivery_date.
    """

    return datetime.combine(
        target_date,
        time.min,
    )


def create_order_number(
    target_date: date,
) -> str:
    """
    Example:

    NM-20260725-A1B2C3D4
    """

    random_part = uuid4().hex[:8].upper()

    return (
        f"NM-{target_date.strftime('%Y%m%d')}-"
        f"{random_part}"
    )


def subscription_is_valid_for_date(
    subscription: Subscription,
    target_date: date,
) -> bool:
    """
    Check whether a subscription is valid for the
    requested order date.
    """

    if subscription.status != SubscriptionStatus.ACTIVE:
        return False

    if subscription.payment_status != PaymentStatus.PAID:
        return False

    if subscription.start_date:
        if subscription.start_date.date() > target_date:
            return False

    if subscription.end_date:
        if subscription.end_date.date() < target_date:
            return False

    return True


def get_existing_daily_order(
    db: Session,
    subscription_id: int,
    target_date: date,
) -> Order | None:
    """
    Find an existing order for the same subscription
    and delivery date.
    """

    normalized_date = normalize_service_datetime(
        target_date
    )

    return (
        db.query(Order)
        .filter(
            Order.subscription_id == subscription_id,
            Order.delivery_date == normalized_date,
        )
        .first()
    )


def get_active_assignments(
    db: Session,
    subscription_id: int,
    target_date: date,
) -> list[MealAssignment]:
    """
    Return active meal assignments for one subscription
    and one delivery date.
    """

    return (
        db.query(MealAssignment)
        .filter(
            MealAssignment.subscription_id
            == subscription_id,
            MealAssignment.delivery_date
            == target_date,
            MealAssignment.is_active.is_(True),
        )
        .order_by(
            MealAssignment.meal_category_id.asc(),
            MealAssignment.id.asc(),
        )
        .all()
    )


def get_delivery_preference(
    db: Session,
    user_id: int,
    meal_category_id: int,
) -> UserCategoryDeliveryPreference | None:
    """
    Return the active delivery preference configured by
    the customer for a particular meal category.
    """

    return (
        db.query(UserCategoryDeliveryPreference)
        .filter(
            UserCategoryDeliveryPreference.user_id
            == user_id,
            UserCategoryDeliveryPreference.meal_category_id
            == meal_category_id,
            UserCategoryDeliveryPreference.is_active.is_(
                True
            ),
        )
        .order_by(
            UserCategoryDeliveryPreference.id.desc()
        )
        .first()
    )


def build_delivery_snapshot(
    preference: UserCategoryDeliveryPreference | None,
    user: User,
) -> dict:
    """
    Build a delivery-location snapshot.

    The snapshot is stored inside Order.items so future
    profile changes do not change existing orders.
    """

    if preference is not None:
        return {
            "delivery_preference_id": preference.id,
            "place_type": enum_value(
                preference.place_type
            ),
            "place_name": preference.place_name,
            "city": preference.city,
            "delivery_area": preference.delivery_area,
            "delivery_address": (
                preference.delivery_address
            ),
            "latitude": preference.latitude,
            "longitude": preference.longitude,
            "preferred_delivery_time": (
                preference.preferred_delivery_time.isoformat()
                if preference.preferred_delivery_time
                else None
            ),
            "delivery_note": preference.delivery_note,
        }

    return {
        "delivery_preference_id": None,
        "place_type": None,
        "place_name": None,
        "city": user.location,
        "delivery_area": None,
        "delivery_address": user.address,
        "latitude": None,
        "longitude": None,
        "preferred_delivery_time": None,
        "delivery_note": None,
    }


def build_assignment_order_item(
    db: Session,
    assignment: MealAssignment,
    user: User,
) -> dict | None:
    """
    Build one immutable Order.items snapshot from one
    MealAssignment.
    """

    meal = (
        db.query(Meal)
        .filter(
            Meal.id == assignment.meal_id
        )
        .first()
    )

    if meal is None:
        return None

    category = (
        db.query(MealCategory)
        .filter(
            MealCategory.id
            == assignment.meal_category_id
        )
        .first()
    )

    delivery_preference = get_delivery_preference(
        db=db,
        user_id=user.id,
        meal_category_id=assignment.meal_category_id,
    )

    delivery_snapshot = build_delivery_snapshot(
        preference=delivery_preference,
        user=user,
    )

    quantity = max(
        int(assignment.quantity or 1),
        1,
    )

    unit_price = float(
        meal.price or 0
    )

    return {
        "assignment_id": assignment.id,
        "meal_id": meal.id,
        "meal_category_id": (
            assignment.meal_category_id
        ),
        "meal_name": meal.name_en,
        "meal_name_ar": meal.name_ar,
        "category_name": (
            category.name_en
            if category
            else None
        ),
        "category_name_ar": (
            category.name_ar
            if category
            else None
        ),
        "quantity": quantity,
        "unit_price": unit_price,
        "line_total": round(
            unit_price * quantity,
            2,
        ),
        "calories": meal.calories,
        "protein_g": meal.protein_g,
        "carbs_g": meal.carbs_g,
        "fat_g": meal.fat_g,
        "fiber_g": meal.fiber_g,
        "sugar_g": meal.sugar_g,
        "sodium_mg": meal.sodium_mg,
        "ingredients": meal.ingredients or [],
        "allergens": meal.allergens or [],
        "diet_tags": meal.diet_tags or [],
        "image_url": meal.image_url,
        "assignment_notes": assignment.notes,
        "delivery": delivery_snapshot,
    }


def build_subscription_order_items(
    db: Session,
    subscription: Subscription,
    target_date: date,
) -> list[dict]:
    """
    Build order items from MealAssignment records.

    This function replaces the old PlanMenuItem logic.
    """

    user = (
        db.query(User)
        .filter(
            User.id == subscription.user_id
        )
        .first()
    )

    if user is None:
        return []

    assignments = get_active_assignments(
        db=db,
        subscription_id=subscription.id,
        target_date=target_date,
    )

    items = []

    for assignment in assignments:
        item = build_assignment_order_item(
            db=db,
            assignment=assignment,
            user=user,
        )

        if item is not None:
            items.append(item)

    return items


def calculate_order_total(
    items: list[dict],
) -> float:
    """
    Calculate the informational meal value.

    The customer already paid for the subscription, so this
    amount is mainly useful for reports and kitchen costing.
    """

    total = sum(
        float(item.get("line_total") or 0)
        for item in items
    )

    return round(total, 2)


def get_unique_delivery_snapshots(
    items: list[dict],
) -> list[dict]:
    """
    Return unique delivery destinations used by the
    assigned meal categories.
    """

    unique_locations = {}

    for item in items:
        delivery = item.get("delivery") or {}

        location_key = (
            delivery.get("delivery_preference_id"),
            delivery.get("place_type"),
            delivery.get("place_name"),
            delivery.get("city"),
            delivery.get("delivery_area"),
            delivery.get("delivery_address"),
            delivery.get("latitude"),
            delivery.get("longitude"),
            delivery.get("preferred_delivery_time"),
        )

        unique_locations[location_key] = delivery

    return list(unique_locations.values())


def build_order_level_delivery(
    items: list[dict],
) -> dict:
    """
    Build order-level delivery fields.

    A customer can use different destinations for breakfast,
    lunch and dinner. Detailed destinations remain inside
    each order item.

    When every item uses the same destination, that
    destination is copied to the main order fields.
    """

    delivery_locations = get_unique_delivery_snapshots(
        items
    )

    if not delivery_locations:
        return {
            "delivery_preference_id": None,
            "delivery_place_type": None,
            "delivery_place_name": None,
            "delivery_city": None,
            "delivery_area": None,
            "delivery_address": None,
            "delivery_latitude": None,
            "delivery_longitude": None,
            "delivery_notes": None,
            "location_count": 0,
        }

    if len(delivery_locations) == 1:
        delivery = delivery_locations[0]

        return {
            "delivery_preference_id": delivery.get(
                "delivery_preference_id"
            ),
            "delivery_place_type": delivery.get(
                "place_type"
            ),
            "delivery_place_name": delivery.get(
                "place_name"
            ),
            "delivery_city": delivery.get("city"),
            "delivery_area": delivery.get(
                "delivery_area"
            ),
            "delivery_address": delivery.get(
                "delivery_address"
            ),
            "delivery_latitude": delivery.get(
                "latitude"
            ),
            "delivery_longitude": delivery.get(
                "longitude"
            ),
            "delivery_notes": delivery.get(
                "delivery_note"
            ),
            "location_count": 1,
        }

    return {
        "delivery_preference_id": None,
        "delivery_place_type": "multiple",
        "delivery_place_name": (
            "Multiple delivery locations"
        ),
        "delivery_city": None,
        "delivery_area": None,
        "delivery_address": (
            "Multiple delivery locations. "
            "See each order item for delivery details."
        ),
        "delivery_latitude": None,
        "delivery_longitude": None,
        "delivery_notes": (
            "This order contains meals assigned to "
            "different delivery locations."
        ),
        "location_count": len(
            delivery_locations
        ),
    }


def order_has_delivery_location(
    items: list[dict],
) -> bool:
    """
    Ensure every assigned meal has at least one delivery
    address.

    The category preference is used first. The customer's
    general address is used as a fallback.
    """

    if not items:
        return False

    for item in items:
        delivery = item.get("delivery") or {}

        if not delivery.get("delivery_address"):
            return False

    return True


def create_daily_order_for_subscription(
    db: Session,
    subscription: Subscription,
    target_date: date,
) -> tuple[Order | None, str]:
    """
    Possible outcomes:

    created
    already_exists
    no_assignments
    invalid_subscription
    user_not_found
    missing_delivery_location
    """

    if not subscription_is_valid_for_date(
        subscription=subscription,
        target_date=target_date,
    ):
        return None, "invalid_subscription"

    existing_order = get_existing_daily_order(
        db=db,
        subscription_id=subscription.id,
        target_date=target_date,
    )

    if existing_order:
        return existing_order, "already_exists"

    user = (
        db.query(User)
        .filter(
            User.id == subscription.user_id
        )
        .first()
    )

    if user is None:
        return None, "user_not_found"

    items = build_subscription_order_items(
        db=db,
        subscription=subscription,
        target_date=target_date,
    )

    if not items:
        return None, "no_assignments"

    if not order_has_delivery_location(items):
        return None, "missing_delivery_location"

    plan = (
        db.query(MealPlan)
        .filter(
            MealPlan.id == subscription.plan_id
        )
        .first()
    )

    delivery_data = build_order_level_delivery(
        items
    )

    order = Order(
        user_id=subscription.user_id,
        subscription_id=subscription.id,
        plan_id=subscription.plan_id,
        order_number=create_order_number(
            target_date
        ),
        source=OrderSource.AUTOMATIC,
        status=(
            OrderStatus.CONFIRMED
            if target_date == date.today()
            else OrderStatus.SCHEDULED
        ),
        total_amount=calculate_order_total(
            items
        ),
        delivery_date=normalize_service_datetime(
            target_date
        ),
        delivery_preference_id=delivery_data[
            "delivery_preference_id"
        ],
        delivery_place_type=delivery_data[
            "delivery_place_type"
        ],
        delivery_place_name=delivery_data[
            "delivery_place_name"
        ],
        delivery_city=delivery_data[
            "delivery_city"
        ],
        delivery_area=delivery_data[
            "delivery_area"
        ],
        delivery_address=delivery_data[
            "delivery_address"
        ],
        delivery_latitude=delivery_data[
            "delivery_latitude"
        ],
        delivery_longitude=delivery_data[
            "delivery_longitude"
        ],
        delivery_notes=(
            delivery_data["delivery_notes"]
            or (
                "Automatically generated from "
                f"{plan.name_en if plan else 'subscription'}"
            )
        ),
        items=items,
        confirmed_at=(
            datetime.utcnow()
            if target_date == date.today()
            else None
        ),
    )

    db.add(order)

    try:
        db.commit()

    except IntegrityError:
        db.rollback()

        existing_order = get_existing_daily_order(
            db=db,
            subscription_id=subscription.id,
            target_date=target_date,
        )

        if existing_order:
            return (
                existing_order,
                "already_exists",
            )

        raise

    db.refresh(order)

    return order, "created"


def confirm_scheduled_orders_for_date(
    db: Session,
    target_date: date,
) -> dict:
    """
    Move scheduled orders to confirmed.
    """

    service_datetime = normalize_service_datetime(
        target_date
    )

    orders = (
        db.query(Order)
        .filter(
            Order.delivery_date
            == service_datetime,
            Order.status
            == OrderStatus.SCHEDULED,
        )
        .all()
    )

    confirmation_time = datetime.utcnow()

    for order in orders:
        order.status = OrderStatus.CONFIRMED
        order.confirmed_at = confirmation_time

    db.commit()

    return {
        "target_date": target_date,
        "orders_confirmed": len(orders),
        "order_ids": [
            order.id
            for order in orders
        ],
    }


def get_subscription_ids_with_assignments(
    db: Session,
    target_date: date,
) -> set[int]:
    """
    Return subscriptions that have active meal assignments
    for the target date.
    """

    rows = (
        db.query(
            MealAssignment.subscription_id
        )
        .filter(
            MealAssignment.delivery_date
            == target_date,
            MealAssignment.is_active.is_(True),
        )
        .distinct()
        .all()
    )

    return {
        row.subscription_id
        for row in rows
    }


def generate_orders_for_date(
    db: Session,
    target_date: date,
) -> dict:
    """
    Generate daily orders from MealAssignment records.
    """

    subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.status
            == SubscriptionStatus.ACTIVE,
            Subscription.payment_status
            == PaymentStatus.PAID,
        )
        .order_by(
            Subscription.id.asc()
        )
        .all()
    )

    subscriptions_with_assignments = (
        get_subscription_ids_with_assignments(
            db=db,
            target_date=target_date,
        )
    )

    result = {
        "target_date": target_date,
        "subscriptions_checked": len(
            subscriptions
        ),
        "subscriptions_with_assignments": len(
            subscriptions_with_assignments
        ),
        "orders_created": 0,
        "already_existing": 0,
        "skipped_no_assignments": 0,
        "skipped_invalid_subscription": 0,
        "skipped_user_not_found": 0,
        "skipped_missing_delivery_location": 0,
        "created_orders": [],
        "skipped": [],
    }

    for subscription in subscriptions:
        order, outcome = (
            create_daily_order_for_subscription(
                db=db,
                subscription=subscription,
                target_date=target_date,
            )
        )

        if outcome == "created":
            order_items = order.items or []

            total_quantity = sum(
                int(item.get("quantity") or 1)
                for item in order_items
            )

            delivery_locations = (
                get_unique_delivery_snapshots(
                    order_items
                )
            )

            result["orders_created"] += 1

            result["created_orders"].append(
                {
                    "order_id": order.id,
                    "order_number": (
                        order.order_number
                    ),
                    "subscription_id": (
                        subscription.id
                    ),
                    "user_id": (
                        subscription.user_id
                    ),
                    "plan_id": (
                        subscription.plan_id
                    ),
                    "status": enum_value(
                        order.status
                    ),
                    "meal_items": len(
                        order_items
                    ),
                    "total_quantity": (
                        total_quantity
                    ),
                    "delivery_locations": len(
                        delivery_locations
                    ),
                }
            )

        elif outcome == "already_exists":
            result["already_existing"] += 1

        elif outcome == "no_assignments":
            result[
                "skipped_no_assignments"
            ] += 1

            result["skipped"].append(
                {
                    "subscription_id": (
                        subscription.id
                    ),
                    "user_id": (
                        subscription.user_id
                    ),
                    "reason": (
                        "No active meal assignments "
                        "exist for this date"
                    ),
                }
            )

        elif outcome == "invalid_subscription":
            result[
                "skipped_invalid_subscription"
            ] += 1

            result["skipped"].append(
                {
                    "subscription_id": (
                        subscription.id
                    ),
                    "user_id": (
                        subscription.user_id
                    ),
                    "reason": (
                        "Subscription is not valid "
                        "for this date"
                    ),
                }
            )

        elif outcome == "user_not_found":
            result[
                "skipped_user_not_found"
            ] += 1

            result["skipped"].append(
                {
                    "subscription_id": (
                        subscription.id
                    ),
                    "user_id": (
                        subscription.user_id
                    ),
                    "reason": (
                        "Customer was not found"
                    ),
                }
            )

        elif outcome == "missing_delivery_location":
            result[
                "skipped_missing_delivery_location"
            ] += 1

            result["skipped"].append(
                {
                    "subscription_id": (
                        subscription.id
                    ),
                    "user_id": (
                        subscription.user_id
                    ),
                    "reason": (
                        "At least one assigned meal "
                        "has no delivery address"
                    ),
                }
            )

    return result


def preview_orders_for_date(
    db: Session,
    target_date: date,
) -> dict:
    """
    Preview orders without inserting anything into the
    database.
    """

    subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.status
            == SubscriptionStatus.ACTIVE,
            Subscription.payment_status
            == PaymentStatus.PAID,
        )
        .order_by(
            Subscription.id.asc()
        )
        .all()
    )

    preview_data = []

    for subscription in subscriptions:
        if not subscription_is_valid_for_date(
            subscription=subscription,
            target_date=target_date,
        ):
            continue

        user = (
            db.query(User)
            .filter(
                User.id == subscription.user_id
            )
            .first()
        )

        if user is None:
            continue

        items = build_subscription_order_items(
            db=db,
            subscription=subscription,
            target_date=target_date,
        )

        if not items:
            continue

        plan = (
            db.query(MealPlan)
            .filter(
                MealPlan.id
                == subscription.plan_id
            )
            .first()
        )

        grouped_locations = defaultdict(list)

        for item in items:
            delivery = item.get("delivery") or {}

            location_key = (
                delivery.get(
                    "delivery_preference_id"
                )
                or (
                    delivery.get(
                        "delivery_address"
                    )
                )
            )

            grouped_locations[
                str(location_key)
            ].append(item)

        preview_data.append(
            {
                "subscription_id": (
                    subscription.id
                ),
                "user_id": user.id,
                "customer": {
                    "id": user.id,
                    "name": (
                        f"{user.first_name} "
                        f"{user.last_name}"
                    ).strip(),
                    "phone": user.phone,
                    "general_address": (
                        user.address
                    ),
                    "allergies": (
                        user.allergies or []
                    ),
                    "dietary_preference": (
                        user.dietary_preference
                    ),
                },
                "plan": (
                    {
                        "id": plan.id,
                        "name": plan.name_en,
                    }
                    if plan
                    else None
                ),
                "meal_count": len(items),
                "total_quantity": sum(
                    int(
                        item.get("quantity")
                        or 1
                    )
                    for item in items
                ),
                "total_amount": (
                    calculate_order_total(
                        items
                    )
                ),
                "has_complete_delivery_locations": (
                    order_has_delivery_location(
                        items
                    )
                ),
                "delivery_location_count": len(
                    grouped_locations
                ),
                "items": items,
            }
        )

    return {
        "target_date": target_date,
        "total_subscriptions": len(
            preview_data
        ),
        "data": preview_data,
    }