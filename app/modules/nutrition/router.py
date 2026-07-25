import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.modules.nutrition.schemas import (
    MenuGenerationRequest,
    MenuGenerationResponse,
)
from app.modules.nutrition.services.menu_generator import (
    MenuGenerator,
)
from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.meal_selections.models import MealSelection
from app.modules.meal_selections.schemas import (
    MealBulkAssignmentRequest,
    MealBulkAssignmentResponse,
    MealSelectionResponse,
    MealSelectionUpdate,
)
from app.modules.meals.models import Meal
from app.modules.nutrition.schemas import (
    MenuGenerationRequest,
    MenuGenerationResponse,
)
from app.modules.nutrition.services.menu_generator import (
    MenuGenerator,
)
from app.modules.subscriptions.models import (
    Subscription,
    SubscriptionStatus,
)
from app.modules.users.models import User, UserRole


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/nutrition",
    tags=["Nutritionist"],
)


MEAL_TIMES = (
    "breakfast",
    "lunch",
    "dinner",
    "snack",
)


NUTRITION_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.NUTRITION_MANAGER,
)


def serialize_assigned_meal(
    selection: MealSelection,
    meal: Meal,
) -> dict:
    return {
        "selection_id": selection.id,
        "subscription_id": selection.subscription_id,
        "plan_id": selection.plan_id,
        "day_number": selection.day_number,
        "meal_time": selection.meal_time,
        "is_skipped": selection.is_skipped,
        "skip_reason": selection.skip_reason,
        "meal": {
            "id": meal.id,
            "category_id": meal.category_id,
            "name_en": meal.name_en,
            "name_ar": meal.name_ar,
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
            "fiber_g": getattr(meal, "fiber_g", None),
            "image_url": meal.image_url,
            "is_available": meal.is_available,
        },
    }
    

NUTRITION_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.NUTRITION_MANAGER,
)


@router.get("/customers")
def list_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*NUTRITION_ROLES)
    ),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
):
    query = db.query(User).filter(
        User.role == UserRole.CUSTOMER
    )

    if search:
        value = f"%{search.strip()}%"

        query = query.filter(
            (User.first_name.ilike(value))
            | (User.last_name.ilike(value))
            | (User.email.ilike(value))
            | (User.phone.ilike(value))
        )

    total = query.count()

    customers = (
        query.order_by(User.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": customers,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (
                (total + limit - 1) // limit
                if total > 0
                else 0
            ),
        },
    }


@router.get("/customers/{user_id}/subscriptions")
def customer_subscriptions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*NUTRITION_ROLES)
    ),
):
    customer = (
        db.query(User)
        .filter(
            User.id == user_id,
            User.role == UserRole.CUSTOMER,
        )
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    subscriptions = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.id.desc())
        .all()
    )

    return subscriptions


@router.get(
    "/subscriptions/{subscription_id}/meal-selections",
    response_model=list[MealSelectionResponse],
)
def subscription_meal_selections(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*NUTRITION_ROLES)
    ),
):
    subscription = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    selections = (
        db.query(MealSelection)
        .filter(
            MealSelection.subscription_id == subscription_id
        )
        .order_by(
            MealSelection.day_number.asc(),
            MealSelection.meal_time.asc(),
            MealSelection.id.asc(),
        )
        .all()
    )

    return selections


@router.post(
    "/subscriptions/{subscription_id}/assign-meal",
    response_model=MealBulkAssignmentResponse,
)
def assign_meals_to_customer_subscription(
    subscription_id: int,
    payload: MealBulkAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*NUTRITION_ROLES)
    ),
):
    """
    Assign multiple meals to one subscription slot.

    One request can contain multiple meal IDs:

    {
        "subscription_id": 1,
        "day_number": 1,
        "meal_time": "breakfast",
        "meal_ids": [3, 5, 8]
    }

    Valid meals are created in one database transaction.
    Invalid or duplicate meals are returned inside errors.
    """

    subscription = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    if payload.subscription_id != subscription_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Payload subscription_id must match "
                "URL subscription_id"
            ),
        )

    requested_meal_ids = payload.meal_ids

    # Fetch every requested meal in one query.
    available_meals = (
        db.query(Meal)
        .filter(
            Meal.id.in_(requested_meal_ids),
            Meal.is_available.is_(True),
        )
        .all()
    )

    available_meal_ids = {
        meal.id for meal in available_meals
    }

    # Find meals already assigned in this slot.
    existing_selections = (
        db.query(MealSelection)
        .filter(
            MealSelection.user_id == subscription.user_id,
            MealSelection.subscription_id == subscription.id,
            MealSelection.day_number == payload.day_number,
            MealSelection.meal_time == payload.meal_time,
            MealSelection.meal_id.in_(requested_meal_ids),
        )
        .all()
    )

    existing_meal_ids = {
        selection.meal_id
        for selection in existing_selections
    }

    created_selections: list[MealSelection] = []
    errors: list[dict] = []

    for meal_id in requested_meal_ids:
        if meal_id not in available_meal_ids:
            errors.append(
                {
                    "meal_id": meal_id,
                    "reason": (
                        "Meal was not found or is unavailable"
                    ),
                }
            )
            continue

        if meal_id in existing_meal_ids:
            errors.append(
                {
                    "meal_id": meal_id,
                    "reason": (
                        "Meal is already assigned for "
                        "this day and meal time"
                    ),
                }
            )
            continue

        selection = MealSelection(
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            plan_id=subscription.plan_id,
            meal_id=meal_id,
            day_number=payload.day_number,
            meal_time=payload.meal_time,
        )

        db.add(selection)
        created_selections.append(selection)

    # Nothing was created.
    if not created_selections:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "No meals were assigned",
                "subscription_id": subscription.id,
                "day_number": payload.day_number,
                "meal_time": payload.meal_time,
                "errors": errors,
            },
        )

    try:
        db.commit()

        for selection in created_selections:
            db.refresh(selection)

    except SQLAlchemyError as exc:
        db.rollback()

        logger.exception(
            "Failed to assign meals to subscription %s",
            subscription_id,
    )

        original_error = getattr(exc, "orig", exc)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save meal assignments: {str(original_error)}",
    ) from exc

    serialized_selections = [
        MealSelectionResponse.model_validate(
            selection
        )
        for selection in created_selections
    ]

    created_count = len(created_selections)
    skipped_count = len(errors)

    if skipped_count > 0:
        message = (
            f"{created_count} meal(s) assigned and "
            f"{skipped_count} meal(s) skipped"
        )
    else:
        message = (
            f"{created_count} meal(s) assigned successfully"
        )

    return {
        "success": True,
        "message": message,
        "subscription_id": subscription.id,
        "day_number": payload.day_number,
        "meal_time": payload.meal_time,
        "requested_count": len(requested_meal_ids),
        "created_count": created_count,
        "skipped_count": skipped_count,
        "created": serialized_selections,
        "errors": errors,
    }
    
    
@router.post(
    "/subscriptions/{subscription_id}/generate-menu",
    response_model=MenuGenerationResponse,
)
def generate_subscription_menu(
    subscription_id: int,
    payload: MenuGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*NUTRITION_ROLES)
    ),
):
    """
    Generate a customer's meal menu.

    Phase 1 supports:
        - single_day

    Future phases will support:
        - repeat_week
        - custom_weeks
    """

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id,
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    generator = MenuGenerator(
        db=db,
        subscription=subscription,
        admin=current_user,
    )

    return generator.generate(payload)    


@router.patch(
    "/meal-selections/{selection_id}",
    response_model=MealSelectionResponse,
)
def update_customer_meal_selection(
    selection_id: int,
    payload: MealSelectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*NUTRITION_ROLES)
    ),
):
    selection = (
        db.query(MealSelection)
        .filter(MealSelection.id == selection_id)
        .first()
    )

    if not selection:
        raise HTTPException(
            status_code=404,
            detail="Meal selection not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    new_meal_id = update_data.get(
        "meal_id",
        selection.meal_id,
    )

    new_day_number = update_data.get(
        "day_number",
        selection.day_number,
    )

    new_meal_time = update_data.get(
        "meal_time",
        selection.meal_time,
    )

    meal = (
        db.query(Meal)
        .filter(
            Meal.id == new_meal_id,
            Meal.is_available.is_(True),
        )
        .first()
    )

    if not meal:
        raise HTTPException(
            status_code=404,
            detail="Meal not found or unavailable",
        )

    duplicate = (
        db.query(MealSelection)
        .filter(
            MealSelection.id != selection.id,
            MealSelection.user_id == selection.user_id,
            MealSelection.subscription_id
            == selection.subscription_id,
            MealSelection.meal_id == new_meal_id,
            MealSelection.day_number == new_day_number,
            MealSelection.meal_time == new_meal_time,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=400,
            detail=(
                "This meal is already assigned for "
                "this day and meal time"
            ),
        )

    for field, value in update_data.items():
        setattr(selection, field, value)

    try:
        db.commit()
        db.refresh(selection)

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to update meal selection",
        ) from exc

    return selection

@router.get(
    "/subscriptions/{subscription_id}/assigned-meals",
)
def get_subscription_assigned_meals(
    subscription_id: int,
    day_number: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
        )
    ),
):
    subscription = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    query = (
        db.query(MealSelection, Meal)
        .join(
            Meal,
            Meal.id == MealSelection.meal_id,
        )
        .filter(
            MealSelection.subscription_id == subscription_id,
        )
    )

    if day_number is not None:
        query = query.filter(
            MealSelection.day_number == day_number,
        )

    results = (
        query.order_by(
            MealSelection.day_number.asc(),
            MealSelection.meal_time.asc(),
            MealSelection.id.asc(),
        )
        .all()
    )

    grouped: dict[str, list[dict]] = {
        meal_time: []
        for meal_time in MEAL_TIMES
    }

    for selection, meal in results:
        grouped.setdefault(
            selection.meal_time,
            [],
        ).append(
            serialize_assigned_meal(
                selection,
                meal,
            )
        )

    return {
        "success": True,
        "subscription_id": subscription.id,
        "user_id": subscription.user_id,
        "plan_id": subscription.plan_id,
        "day_number": day_number,
        "assigned_meals": grouped,
    }
    
@router.post(
    "/subscriptions/{subscription_id}/generate-menu",
    response_model=MenuGenerationResponse,
)
def generate_subscription_menu(
    subscription_id: int,
    payload: MenuGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*NUTRITION_ROLES)
    ),
):
    """
    Generate a menu for a paid customer subscription.

    Supported modes:

        single_day
            Generate one absolute subscription day.

        repeat_week
            Create one seven-day subscription template and repeat it
            until the subscription ends.

        custom_weeks
            Create a different menu for each subscription week.
    """

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id,
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    generator = MenuGenerator(
        db=db,
        subscription=subscription,
        admin=current_user,
    )

    return generator.generate(payload)    

@router.delete("/meal-selections/{selection_id}")
def delete_customer_meal_selection(
    selection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*NUTRITION_ROLES)
    ),
):
    selection = (
        db.query(MealSelection)
        .filter(MealSelection.id == selection_id)
        .first()
    )

    if not selection:
        raise HTTPException(
            status_code=404,
            detail="Meal selection not found",
        )

    try:
        db.delete(selection)
        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to delete meal selection",
        ) from exc

    return {
        "success": True,
        "message": "Meal selection deleted successfully",
    }