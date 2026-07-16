from __future__ import annotations

from datetime import date, datetime, time
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.meals.models import Meal, MealCategory
from app.modules.orders.models import Order, OrderStatus
from app.modules.plan_menus.models import (
    PlanMenuItem,
    WeekDay,
)
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import (
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.users.models import User


WEEKDAY_MAPPING = {
    0: WeekDay.MONDAY,
    1: WeekDay.TUESDAY,
    2: WeekDay.WEDNESDAY,
    3: WeekDay.THURSDAY,
    4: WeekDay.FRIDAY,
    5: WeekDay.SATURDAY,
    6: WeekDay.SUNDAY,
}


def normalize_service_datetime(
    target_date: date,
) -> datetime:
    """
    Store automatic delivery dates at midnight so duplicate checks
    remain predictable.
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
    NM-20260720-A1B2C3D4
    """

    random_part = uuid4().hex[:8].upper()

    return (
        f"NM-{target_date.strftime('%Y%m%d')}-"
        f"{random_part}"
    )


def enum_value(value):
    if value is None:
        return None

    return (
        value.value
        if hasattr(value, "value")
        else value
    )


def subscription_is_valid_for_date(
    subscription: Subscription,
    target_date: date,
) -> bool:
    """
    Check whether the subscription should receive meals
    on the requested date.
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


def build_order_item(
    menu_item: PlanMenuItem,
    meal: Meal,
    category: MealCategory | None,
) -> dict:
    """
    Create the JSON snapshot stored in Order.items.

    This keeps historical order information even if the admin
    later updates the meal.
    """

    quantity = max(menu_item.quantity or 1, 1)

    unit_price = float(
        getattr(meal, "price", 0) or 0
    )

    return {
        "plan_menu_item_id": menu_item.id,
        "meal_id": meal.id,
        "meal_name": meal.name_en,
        "meal_name_ar": getattr(
            meal,
            "name_ar",
            None,
        ),

        "category_id": menu_item.category_id,
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

        "day_of_week": enum_value(
            menu_item.day_of_week
        ),

        "quantity": quantity,
        "unit_price": unit_price,
        "line_total": unit_price * quantity,

        "calories": getattr(
            meal,
            "calories",
            None,
        ),
        "protein_g": getattr(
            meal,
            "protein_g",
            None,
        ),
        "carbs_g": getattr(
            meal,
            "carbs_g",
            None,
        ),
        "fat_g": getattr(
            meal,
            "fat_g",
            None,
        ),

        "ingredients": getattr(
            meal,
            "ingredients",
            None,
        ) or [],

        "allergens": getattr(
            meal,
            "allergens",
            None,
        ) or [],

        "image_url": getattr(
            meal,
            "image_url",
            None,
        ),
    }


def build_subscription_order_items(
    db: Session,
    subscription: Subscription,
    target_date: date,
) -> list[dict]:
    weekday = WEEKDAY_MAPPING[
        target_date.weekday()
    ]

    menu_items = (
        db.query(PlanMenuItem)
        .filter(
            PlanMenuItem.plan_id
            == subscription.plan_id,
            PlanMenuItem.day_of_week
            == weekday,
            PlanMenuItem.is_active.is_(True),
        )
        .order_by(
            PlanMenuItem.sort_order.asc(),
            PlanMenuItem.id.asc(),
        )
        .all()
    )

    result: list[dict] = []

    for menu_item in menu_items:
        meal = (
            db.query(Meal)
            .filter(
                Meal.id == menu_item.meal_id,
                Meal.is_available.is_(True),
            )
            .first()
        )

        if meal is None:
            continue

        category = (
            db.query(MealCategory)
            .filter(
                MealCategory.id
                == menu_item.category_id
            )
            .first()
        )

        result.append(
            build_order_item(
                menu_item=menu_item,
                meal=meal,
                category=category,
            )
        )

    return result


def calculate_order_total(
    items: list[dict],
) -> float:
    return round(
        sum(
            float(item.get("line_total") or 0)
            for item in items
        ),
        2,
    )


def create_daily_order_for_subscription(
    db: Session,
    subscription: Subscription,
    target_date: date,
) -> tuple[Order | None, str]:
    """
    Return:
        (order, "created")
        (existing_order, "already_exists")
        (None, "no_menu")
        (None, "invalid_subscription")
        (None, "user_not_found")
        (None, "address_missing")
    """

    if not subscription_is_valid_for_date(
        subscription,
        target_date,
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
        .filter(User.id == subscription.user_id)
        .first()
    )

    if user is None:
        return None, "user_not_found"

    delivery_address = getattr(
        user,
        "address",
        None,
    )

    if not delivery_address:
        return None, "address_missing"

    items = build_subscription_order_items(
        db=db,
        subscription=subscription,
        target_date=target_date,
    )

    if not items:
        return None, "no_menu"

    plan = (
        db.query(MealPlan)
        .filter(
            MealPlan.id
            == subscription.plan_id
        )
        .first()
    )

    order = Order(
        user_id=subscription.user_id,
        subscription_id=subscription.id,
        plan_id=subscription.plan_id,

        order_number=create_order_number(
            target_date
        ),

        # Future orders are scheduled.
        # Today's generated orders are confirmed immediately.
        status=(
            OrderStatus.CONFIRMED
            if target_date == date.today()
            else OrderStatus.SCHEDULED
        ),

        # The customer already paid for the subscription.
        # This amount is informational for kitchen/order reporting.
        total_amount=calculate_order_total(items),

        delivery_date=normalize_service_datetime(
            target_date
        ),

        delivery_address=delivery_address,

        delivery_notes=(
            f"Automatically generated from "
            f"{plan.name_en if plan else 'subscription plan'}"
        ),

        items=items,
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
            return existing_order, "already_exists"

        raise

    db.refresh(order)

    return order, "created"


def confirm_scheduled_orders_for_date(
    db: Session,
    target_date: date,
) -> dict:
    service_datetime = (
        normalize_service_datetime(
            target_date
        )
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

    for order in orders:
        order.status = OrderStatus.CONFIRMED

    db.commit()

    return {
        "target_date": target_date,
        "orders_confirmed": len(orders),
        "order_ids": [
            order.id
            for order in orders
        ],
    }


def generate_orders_for_date(
    db: Session,
    target_date: date,
) -> dict:
    subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.status
            == SubscriptionStatus.ACTIVE,
            Subscription.payment_status
            == PaymentStatus.PAID,
        )
        .order_by(Subscription.id.asc())
        .all()
    )

    result = {
        "target_date": target_date,
        "weekday": WEEKDAY_MAPPING[
            target_date.weekday()
        ].value,
        "subscriptions_checked": len(
            subscriptions
        ),
        "orders_created": 0,
        "already_existing": 0,
        "skipped_no_menu": 0,
        "skipped_invalid_subscription": 0,
        "skipped_user_not_found": 0,
        "skipped_address_missing": 0,
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
                        order.items or []
                    ),
                }
            )

        elif outcome == "already_exists":
            result["already_existing"] += 1

        elif outcome == "no_menu":
            result["skipped_no_menu"] += 1

            result["skipped"].append(
                {
                    "subscription_id": subscription.id,
                    "reason": "No active menu exists for this weekday",
                }
            )

        elif outcome == "invalid_subscription":
            result[
                "skipped_invalid_subscription"
            ] += 1

        elif outcome == "user_not_found":
            result[
                "skipped_user_not_found"
            ] += 1

        elif outcome == "address_missing":
            result[
                "skipped_address_missing"
            ] += 1

            result["skipped"].append(
                {
                    "subscription_id": subscription.id,
                    "user_id": subscription.user_id,
                    "reason": "Customer delivery address is missing",
                }
            )

    return result