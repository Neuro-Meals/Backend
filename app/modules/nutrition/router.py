from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.meal_selections.models import MealSelection
from app.modules.meal_selections.schemas import (
    MealSelectionCreate,
    MealSelectionResponse,
    MealSelectionUpdate,
)
from app.modules.meals.models import Meal
from app.modules.plans.models import MealPlanItem
from app.modules.subscriptions.models import Subscription
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/nutrition", tags=["Nutritionist"])


NUTRITION_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.NUTRITION_MANAGER,
)


@router.get("/customers")
def list_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*NUTRITION_ROLES)),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(User).filter(User.role == UserRole.CUSTOMER)

    if search:
        value = f"%{search}%"
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
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/customers/{user_id}/subscriptions")
def customer_subscriptions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*NUTRITION_ROLES)),
):
    customer = db.query(User).filter(
        User.id == user_id,
        User.role == UserRole.CUSTOMER,
    ).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.id.desc())
        .all()
    )


@router.get("/subscriptions/{subscription_id}/meal-selections")
def subscription_meal_selections(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*NUTRITION_ROLES)),
):
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return (
        db.query(MealSelection)
        .filter(MealSelection.subscription_id == subscription_id)
        .order_by(MealSelection.day_number.asc(), MealSelection.meal_time.asc())
        .all()
    )


@router.post("/subscriptions/{subscription_id}/assign-meal", response_model=MealSelectionResponse)
def assign_meal_to_customer_subscription(
    subscription_id: int,
    payload: MealSelectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*NUTRITION_ROLES)),
):
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if payload.subscription_id != subscription_id:
        raise HTTPException(
            status_code=400,
            detail="Payload subscription_id must match URL subscription_id",
        )

    meal = db.query(Meal).filter(
        Meal.id == payload.meal_id,
        Meal.is_available == True,
    ).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found or unavailable")

    allowed_meal = db.query(MealPlanItem).filter(
        MealPlanItem.plan_id == subscription.plan_id,
        MealPlanItem.meal_id == payload.meal_id,
        MealPlanItem.day_number == payload.day_number,
        MealPlanItem.meal_time == payload.meal_time,
        MealPlanItem.is_active == True,
    ).first()

    if not allowed_meal:
        raise HTTPException(
            status_code=400,
            detail="This meal is not available in this plan slot",
        )

    existing = db.query(MealSelection).filter(
        MealSelection.user_id == subscription.user_id,
        MealSelection.subscription_id == subscription.id,
        MealSelection.day_number == payload.day_number,
        MealSelection.meal_time == payload.meal_time,
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Customer already has a meal selected for this day and time",
        )

    selection = MealSelection(
        user_id=subscription.user_id,
        subscription_id=subscription.id,
        plan_id=subscription.plan_id,
        meal_id=payload.meal_id,
        day_number=payload.day_number,
        meal_time=payload.meal_time,
    )

    db.add(selection)
    db.commit()
    db.refresh(selection)

    return selection


@router.patch("/meal-selections/{selection_id}", response_model=MealSelectionResponse)
def update_customer_meal_selection(
    selection_id: int,
    payload: MealSelectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*NUTRITION_ROLES)),
):
    selection = db.query(MealSelection).filter(MealSelection.id == selection_id).first()

    if not selection:
        raise HTTPException(status_code=404, detail="Meal selection not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "meal_id" in update_data and update_data["meal_id"] is not None:
        allowed_meal = db.query(MealPlanItem).filter(
            MealPlanItem.plan_id == selection.plan_id,
            MealPlanItem.meal_id == update_data["meal_id"],
            MealPlanItem.day_number == selection.day_number,
            MealPlanItem.meal_time == selection.meal_time,
            MealPlanItem.is_active == True,
        ).first()

        if not allowed_meal:
            raise HTTPException(
                status_code=400,
                detail="This meal is not available in this plan slot",
            )

    for field, value in update_data.items():
        setattr(selection, field, value)

    db.commit()
    db.refresh(selection)

    return selection


@router.delete("/meal-selections/{selection_id}")
def delete_customer_meal_selection(
    selection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*NUTRITION_ROLES)),
):
    selection = db.query(MealSelection).filter(MealSelection.id == selection_id).first()

    if not selection:
        raise HTTPException(status_code=404, detail="Meal selection not found")

    db.delete(selection)
    db.commit()

    return {"message": "Meal selection deleted successfully"}