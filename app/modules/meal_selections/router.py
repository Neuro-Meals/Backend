from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.meal_selections.models import MealSelection
from app.modules.meal_selections.schemas import (
    MealSelectionCreate,
    MealSelectionResponse,
    MealSelectionUpdate,
)
from app.modules.meals.models import Meal
from app.modules.plans.models import MealPlanItem
from app.modules.subscriptions.models import Subscription, SubscriptionStatus
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/meal-selections", tags=["Meal Selections"])


@router.post("/", response_model=MealSelectionResponse)
def create_meal_selection(
    payload: MealSelectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = db.query(Subscription).filter(
        Subscription.id == payload.subscription_id,
        Subscription.user_id == current_user.id,
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if subscription.status not in [
        SubscriptionStatus.PENDING_PAYMENT,
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAUSED,
    ]:
        raise HTTPException(status_code=400, detail="Subscription is not selectable")

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
        MealSelection.user_id == current_user.id,
        MealSelection.subscription_id == subscription.id,
        MealSelection.day_number == payload.day_number,
        MealSelection.meal_time == payload.meal_time,
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already selected a meal for this day and time",
        )

    selection = MealSelection(
        user_id=current_user.id,
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


@router.get("/my")
def my_meal_selections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    subscription_id: int | None = Query(None),
):
    query = db.query(MealSelection).filter(MealSelection.user_id == current_user.id)

    if subscription_id:
        query = query.filter(MealSelection.subscription_id == subscription_id)

    return query.order_by(
        MealSelection.day_number.asc(),
        MealSelection.meal_time.asc(),
    ).all()


@router.put("/{selection_id}", response_model=MealSelectionResponse)
def update_meal_selection(
    selection_id: int,
    payload: MealSelectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    selection = db.query(MealSelection).filter(
        MealSelection.id == selection_id,
        MealSelection.user_id == current_user.id,
    ).first()

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


@router.delete("/{selection_id}")
def delete_meal_selection(
    selection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    selection = db.query(MealSelection).filter(
        MealSelection.id == selection_id,
        MealSelection.user_id == current_user.id,
    ).first()

    if not selection:
        raise HTTPException(status_code=404, detail="Meal selection not found")

    db.delete(selection)
    db.commit()

    return {"message": "Meal selection deleted successfully"}


@router.get("/")
def admin_list_meal_selections(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.NUTRITION_MANAGER)
    ),
    user_id: int | None = Query(None),
    subscription_id: int | None = Query(None),
    plan_id: int | None = Query(None),
):
    query = db.query(MealSelection)

    if user_id:
        query = query.filter(MealSelection.user_id == user_id)

    if subscription_id:
        query = query.filter(MealSelection.subscription_id == subscription_id)

    if plan_id:
        query = query.filter(MealSelection.plan_id == plan_id)

    return query.order_by(MealSelection.id.desc()).all()