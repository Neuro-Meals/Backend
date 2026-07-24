from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.meal_assignments.models import (
    MealAssignment,
    MealAssignmentItem,
)
from app.modules.orders.models import (
    Order,
    OrderSource,
    OrderStatus,
)
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


def value_is_equal(value, expected) -> bool:
    left = enum_value(value)
    right = enum_value(expected)
    if left is None or right is None:
        return left == right
    return str(left).strip().lower() == str(right).strip().lower()


def date_only(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def create_order_number(target_date: date) -> str:
    return f"NM-{target_date.strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"


def full_name(user: User | None) -> str | None:
    if user is None:
        return None
    name = " ".join(
        part
        for part in [
            getattr(user, "first_name", None),
            getattr(user, "last_name", None),
        ]
        if part
    ).strip()
    return name or None


def subscription_is_valid_for_date(
    subscription: Subscription,
    target_date: date,
) -> bool:
    if not value_is_equal(subscription.status, SubscriptionStatus.ACTIVE):
        return False
    if not value_is_equal(subscription.payment_status, PaymentStatus.PAID):
        return False

    start_date = date_only(getattr(subscription, "start_date", None))
    end_date = date_only(getattr(subscription, "end_date", None))

    if start_date is not None and start_date > target_date:
        return False
    if end_date is not None and end_date < target_date:
        return False
    return True


def assignment_query(db: Session):
    return (
        db.query(MealAssignment)
        .options(
            selectinload(MealAssignment.items).selectinload(
                MealAssignmentItem.meal
            ),
            selectinload(MealAssignment.category),
            selectinload(MealAssignment.customer),
            selectinload(MealAssignment.driver),
            selectinload(MealAssignment.subscription),
            selectinload(MealAssignment.delivery_preference),
        )
    )


def get_assignment_by_id(
    db: Session,
    assignment_id: int,
) -> MealAssignment | None:
    return (
        assignment_query(db)
        .filter(MealAssignment.id == assignment_id)
        .first()
    )


def get_active_assignments_for_date(
    db: Session,
    target_date: date,
) -> list[MealAssignment]:
    return (
        assignment_query(db)
        .filter(
            MealAssignment.delivery_date == target_date,
            MealAssignment.is_active.is_(True),
        )
        .order_by(
            MealAssignment.subscription_id.asc(),
            MealAssignment.delivery_time.asc(),
            MealAssignment.meal_category_id.asc(),
            MealAssignment.id.asc(),
        )
        .all()
    )


def get_active_assignments(
    db: Session,
    subscription_id: int,
    target_date: date,
) -> list[MealAssignment]:
    return (
        assignment_query(db)
        .filter(
            MealAssignment.subscription_id == subscription_id,
            MealAssignment.delivery_date == target_date,
            MealAssignment.is_active.is_(True),
        )
        .order_by(
            MealAssignment.delivery_time.asc(),
            MealAssignment.meal_category_id.asc(),
            MealAssignment.id.asc(),
        )
        .all()
    )


def get_existing_order_for_assignment(
    db: Session,
    meal_assignment_id: int,
) -> Order | None:
    return (
        db.query(Order)
        .filter(Order.meal_assignment_id == meal_assignment_id)
        .first()
    )


def get_existing_daily_order(
    db: Session,
    subscription_id: int,
    target_date: date,
) -> Order | None:
    return (
        db.query(Order)
        .filter(
            Order.subscription_id == subscription_id,
            Order.delivery_date == target_date,
        )
        .order_by(Order.id.asc())
        .first()
    )


def build_delivery_snapshot(assignment: MealAssignment) -> dict:
    preference = assignment.delivery_preference

    if preference is None:
        return {
            "delivery_preference_id": assignment.delivery_preference_id,
            "place_type": None,
            "place_name": None,
            "city": None,
            "delivery_area": None,
            "delivery_address": None,
            "latitude": None,
            "longitude": None,
            "preferred_delivery_time": (
                assignment.delivery_time.isoformat()
                if assignment.delivery_time
                else None
            ),
            "delivery_note": assignment.notes,
        }

    preferred_time = getattr(preference, "preferred_delivery_time", None)

    return {
        "delivery_preference_id": preference.id,
        "place_type": enum_value(getattr(preference, "place_type", None)),
        "place_name": getattr(preference, "place_name", None),
        "city": getattr(preference, "city", None),
        "delivery_area": getattr(preference, "delivery_area", None),
        "delivery_address": getattr(preference, "delivery_address", None),
        "latitude": getattr(preference, "latitude", None),
        "longitude": getattr(preference, "longitude", None),
        "preferred_delivery_time": (
            preferred_time.isoformat()
            if preferred_time
            else (
                assignment.delivery_time.isoformat()
                if assignment.delivery_time
                else None
            )
        ),
        "delivery_note": (
            assignment.notes
            or getattr(preference, "delivery_note", None)
        ),
    }


def build_driver_snapshot(assignment: MealAssignment) -> dict:
    driver = assignment.driver
    return {
        "driver_id": assignment.driver_id,
        "driver_name": full_name(driver),
        "driver_phone": getattr(driver, "phone", None) if driver else None,
        "driver_email": getattr(driver, "email", None) if driver else None,
    }


def build_customer_snapshot(assignment: MealAssignment) -> dict:
    customer = assignment.customer
    return {
        "user_id": assignment.user_id,
        "customer_name": full_name(customer),
        "customer_phone": getattr(customer, "phone", None) if customer else None,
        "customer_email": getattr(customer, "email", None) if customer else None,
        "allergies": getattr(customer, "allergies", None) or [] if customer else [],
        "dietary_preference": (
            getattr(customer, "dietary_preference", None)
            if customer
            else None
        ),
    }


def build_category_snapshot(assignment: MealAssignment) -> dict:
    category = assignment.category
    return {
        "meal_category_id": assignment.meal_category_id,
        "category_name": getattr(category, "name_en", None) if category else None,
        "category_name_ar": getattr(category, "name_ar", None) if category else None,
    }


def build_meal_item_snapshot(
    assignment_item: MealAssignmentItem,
) -> dict | None:
    meal = assignment_item.meal
    if meal is None:
        return None

    quantity = max(int(assignment_item.quantity or 1), 1)
    unit_price = float(getattr(meal, "price", 0) or 0)

    return {
        "meal_assignment_item_id": assignment_item.id,
        "meal_id": meal.id,
        "meal_name": getattr(meal, "name_en", None),
        "meal_name_ar": getattr(meal, "name_ar", None),
        "description": getattr(meal, "description", None),
        "quantity": quantity,
        "unit_price": unit_price,
        "line_total": round(unit_price * quantity, 2),
        "calories": getattr(meal, "calories", None),
        "protein_g": getattr(meal, "protein_g", getattr(meal, "protein", None)),
        "carbs_g": getattr(meal, "carbs_g", getattr(meal, "carbs", None)),
        "fat_g": getattr(meal, "fat_g", getattr(meal, "fat", None)),
        "fiber_g": getattr(meal, "fiber_g", None),
        "sugar_g": getattr(meal, "sugar_g", None),
        "sodium_mg": getattr(meal, "sodium_mg", None),
        "ingredients": getattr(meal, "ingredients", None) or [],
        "allergens": getattr(meal, "allergens", None) or [],
        "diet_tags": getattr(meal, "diet_tags", None) or [],
        "image_url": getattr(meal, "image_url", None),
        "notes": assignment_item.notes,
    }


def build_assignment_order_items(
    assignment: MealAssignment,
) -> list[dict]:
    items = []
    for assignment_item in assignment.items or []:
        snapshot = build_meal_item_snapshot(assignment_item)
        if snapshot is not None:
            items.append(snapshot)
    return items


def calculate_order_total(items: list[dict]) -> float:
    return round(
        sum(float(item.get("line_total") or 0) for item in items),
        2,
    )


def order_has_delivery_location(assignment_or_items) -> bool:
    if isinstance(assignment_or_items, MealAssignment):
        delivery = build_delivery_snapshot(assignment_or_items)
        return bool(delivery.get("delivery_address"))

    items = assignment_or_items or []
    if not items:
        return False

    for item in items:
        delivery = item.get("delivery") or {}
        if not delivery.get("delivery_address"):
            return False
    return True


def create_order_for_assignment(
    db: Session,
    assignment: MealAssignment,
    *,
    commit: bool = True,
) -> tuple[Order | None, str]:
    if not assignment.is_active:
        return None, "inactive_assignment"

    existing_order = get_existing_order_for_assignment(
        db=db,
        meal_assignment_id=assignment.id,
    )
    if existing_order is not None:
        return existing_order, "already_exists"

    subscription = assignment.subscription
    if subscription is None:
        subscription = (
            db.query(Subscription)
            .filter(Subscription.id == assignment.subscription_id)
            .first()
        )

    if subscription is None:
        return None, "invalid_subscription"

    if not subscription_is_valid_for_date(
        subscription=subscription,
        target_date=assignment.delivery_date,
    ):
        return None, "invalid_subscription"

    if assignment.customer is None:
        return None, "missing_customer"
    if assignment.driver is None:
        return None, "missing_driver"
    if assignment.delivery_preference is None:
        return None, "missing_delivery_preference"
    if assignment.delivery_time is None:
        return None, "missing_delivery_time"

    order_items = build_assignment_order_items(assignment)
    if not order_items:
        return None, "no_meals"

    delivery = build_delivery_snapshot(assignment)
    if not delivery.get("delivery_address"):
        return None, "missing_delivery_location"

    category_snapshot = build_category_snapshot(assignment)
    driver_snapshot = build_driver_snapshot(assignment)
    customer_snapshot = build_customer_snapshot(assignment)

    snapshot_items = [
        {
            **item,
            "meal_assignment_id": assignment.id,
            **category_snapshot,
            "delivery": delivery,
            "driver": driver_snapshot,
            "customer": customer_snapshot,
            "assignment_notes": assignment.notes,
        }
        for item in order_items
    ]

    initial_status = (
        OrderStatus.CONFIRMED
        if assignment.delivery_date <= date.today()
        else OrderStatus.SCHEDULED
    )

    order = Order(
        order_number=create_order_number(assignment.delivery_date),
        user_id=assignment.user_id,
        subscription_id=assignment.subscription_id,
        plan_id=getattr(subscription, "plan_id", None),
        meal_assignment_id=assignment.id,
        meal_category_id=assignment.meal_category_id,
        driver_id=assignment.driver_id,
        delivery_preference_id=assignment.delivery_preference_id,
        source=OrderSource.AUTOMATIC,
        status=initial_status,
        delivery_date=assignment.delivery_date,
        delivery_time=assignment.delivery_time,
        total_amount=calculate_order_total(order_items),
        items=snapshot_items,
        delivery_place_type=delivery.get("place_type"),
        delivery_place_name=delivery.get("place_name"),
        delivery_city=delivery.get("city"),
        delivery_area=delivery.get("delivery_area"),
        delivery_address=delivery["delivery_address"],
        delivery_latitude=delivery.get("latitude"),
        delivery_longitude=delivery.get("longitude"),
        delivery_notes=delivery.get("delivery_note"),
        confirmed_at=(
            datetime.utcnow()
            if initial_status == OrderStatus.CONFIRMED
            else None
        ),
    )

    db.add(order)

    try:
        if commit:
            db.commit()
            db.refresh(order)
        else:
            db.flush()
    except IntegrityError:
        db.rollback()
        existing_order = get_existing_order_for_assignment(
            db=db,
            meal_assignment_id=assignment.id,
        )
        if existing_order is not None:
            return existing_order, "already_exists"
        raise

    return order, "created"


def create_daily_order_for_subscription(
    db: Session,
    subscription: Subscription,
    target_date: date,
) -> tuple[Order | None, str]:
    if not subscription_is_valid_for_date(subscription, target_date):
        return None, "invalid_subscription"

    assignments = get_active_assignments(
        db=db,
        subscription_id=subscription.id,
        target_date=target_date,
    )
    if not assignments:
        return None, "no_assignments"

    first_order = None
    created_count = 0

    for assignment in assignments:
        order, outcome = create_order_for_assignment(db, assignment)
        if order is not None and first_order is None:
            first_order = order
        if outcome == "created":
            created_count += 1

    if created_count > 0:
        return first_order, "created"
    if first_order is not None:
        return first_order, "already_exists"
    return None, "no_orders_created"


def outcome_message(outcome: str) -> str:
    messages = {
        "already_exists": "An order already exists for this meal assignment",
        "inactive_assignment": "Meal assignment is inactive",
        "invalid_subscription": "Subscription is missing, unpaid, inactive, or outside its valid date range",
        "no_meals": "Meal assignment contains no valid meal items",
        "missing_customer": "Customer record was not found",
        "missing_driver": "Assigned driver was not found",
        "missing_delivery_preference": "Selected delivery preference was not found",
        "missing_delivery_location": "Selected delivery preference has no address",
        "missing_delivery_time": "Meal assignment has no delivery time",
    }
    return messages.get(outcome, outcome.replace("_", " ").capitalize())


def serialize_created_order(order: Order) -> dict:
    items = order.items or []
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "meal_assignment_id": order.meal_assignment_id,
        "subscription_id": order.subscription_id,
        "user_id": order.user_id,
        "plan_id": order.plan_id,
        "meal_category_id": order.meal_category_id,
        "driver_id": order.driver_id,
        "delivery_preference_id": order.delivery_preference_id,
        "delivery_date": order.delivery_date,
        "delivery_time": order.delivery_time,
        "status": enum_value(order.status),
        "meal_items": len(items),
        "total_quantity": sum(int(item.get("quantity") or 1) for item in items),
        "total_amount": order.total_amount,
    }


def generate_orders_for_date(
    db: Session,
    target_date: date,
) -> dict:
    assignments = get_active_assignments_for_date(db, target_date)

    result = {
        "target_date": target_date,
        "assignments_checked": len(assignments),
        "orders_created": 0,
        "already_existing": 0,
        "skipped_inactive_assignment": 0,
        "skipped_invalid_subscription": 0,
        "skipped_no_meals": 0,
        "skipped_missing_customer": 0,
        "skipped_missing_driver": 0,
        "skipped_missing_delivery_preference": 0,
        "skipped_missing_delivery_location": 0,
        "skipped_missing_delivery_time": 0,
        "created_orders": [],
        "existing_orders": [],
        "skipped": [],
    }

    for assignment in assignments:
        order, outcome = create_order_for_assignment(db, assignment)

        if outcome == "created":
            result["orders_created"] += 1
            result["created_orders"].append(serialize_created_order(order))
            continue

        if outcome == "already_exists":
            result["already_existing"] += 1
            if order is not None:
                result["existing_orders"].append(serialize_created_order(order))
            continue

        counter_key = f"skipped_{outcome}"
        if counter_key in result:
            result[counter_key] += 1

        result["skipped"].append(
            {
                "meal_assignment_id": assignment.id,
                "subscription_id": assignment.subscription_id,
                "user_id": assignment.user_id,
                "meal_category_id": assignment.meal_category_id,
                "reason_code": outcome,
                "reason": outcome_message(outcome),
            }
        )

    return result


def preview_assignment_order(assignment: MealAssignment) -> dict:
    order_items = build_assignment_order_items(assignment)
    delivery = build_delivery_snapshot(assignment)

    return {
        "meal_assignment_id": assignment.id,
        "subscription_id": assignment.subscription_id,
        "user_id": assignment.user_id,
        "customer": build_customer_snapshot(assignment),
        "plan_id": (
            getattr(assignment.subscription, "plan_id", None)
            if assignment.subscription
            else None
        ),
        "meal_category": build_category_snapshot(assignment),
        "driver": build_driver_snapshot(assignment),
        "delivery_preference_id": assignment.delivery_preference_id,
        "delivery_date": assignment.delivery_date,
        "delivery_time": assignment.delivery_time,
        "delivery": delivery,
        "assignment_notes": assignment.notes,
        "meal_count": len(order_items),
        "total_quantity": sum(int(item.get("quantity") or 1) for item in order_items),
        "total_amount": calculate_order_total(order_items),
        "has_delivery_location": bool(delivery.get("delivery_address")),
        "has_driver": assignment.driver is not None,
        "subscription_is_valid": (
            assignment.subscription is not None
            and subscription_is_valid_for_date(
                assignment.subscription,
                assignment.delivery_date,
            )
        ),
        "items": order_items,
        "existing_order": None,
    }


def preview_orders_for_date(
    db: Session,
    target_date: date,
) -> dict:
    assignments = get_active_assignments_for_date(db, target_date)
    data = []

    for assignment in assignments:
        preview = preview_assignment_order(assignment)
        existing_order = get_existing_order_for_assignment(db, assignment.id)

        preview["existing_order"] = (
            {
                "id": existing_order.id,
                "order_number": existing_order.order_number,
                "status": enum_value(existing_order.status),
            }
            if existing_order
            else None
        )
        data.append(preview)

    return {
        "target_date": target_date,
        "total_assignments": len(assignments),
        "orders_already_existing": sum(
            1 for item in data if item["existing_order"] is not None
        ),
        "orders_ready_to_create": sum(
            1
            for item in data
            if (
                item["existing_order"] is None
                and item["meal_count"] > 0
                and item["has_delivery_location"]
                and item["has_driver"]
                and item["subscription_is_valid"]
            )
        ),
        "data": data,
    }


def confirm_scheduled_orders_for_date(
    db: Session,
    target_date: date,
) -> dict:
    orders = (
        db.query(Order)
        .filter(
            Order.delivery_date == target_date,
            Order.status == OrderStatus.SCHEDULED,
        )
        .order_by(Order.delivery_time.asc(), Order.id.asc())
        .all()
    )

    confirmation_time = datetime.utcnow()
    for order in orders:
        order.status = OrderStatus.CONFIRMED
        order.confirmed_at = confirmation_time

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "target_date": target_date,
        "orders_confirmed": len(orders),
        "order_ids": [order.id for order in orders],
        "order_numbers": [order.order_number for order in orders],
    }


def generate_and_confirm_orders_for_date(
    db: Session,
    target_date: date,
) -> dict:
    generation = generate_orders_for_date(db, target_date)

    confirmation = {
        "target_date": target_date,
        "orders_confirmed": 0,
        "order_ids": [],
        "order_numbers": [],
    }

    if target_date <= date.today():
        confirmation = confirm_scheduled_orders_for_date(db, target_date)

    return {
        "target_date": target_date,
        "generation": generation,
        "confirmation": confirmation,
    }


def get_orders_for_assignment_date(
    db: Session,
    target_date: date,
) -> list[Order]:
    return (
        db.query(Order)
        .filter(Order.delivery_date == target_date)
        .order_by(
            Order.delivery_time.asc(),
            Order.meal_category_id.asc(),
            Order.id.asc(),
        )
        .all()
    )


def get_assignment_ids_with_orders(
    db: Session,
    target_date: date,
) -> set[int]:
    rows = (
        db.query(Order.meal_assignment_id)
        .filter(Order.delivery_date == target_date)
        .all()
    )
    return {row.meal_assignment_id for row in rows}


def get_subscription_ids_with_assignments(
    db: Session,
    target_date: date,
) -> set[int]:
    rows = (
        db.query(MealAssignment.subscription_id)
        .filter(
            MealAssignment.delivery_date == target_date,
            MealAssignment.is_active.is_(True),
        )
        .distinct()
        .all()
    )
    return {row.subscription_id for row in rows}