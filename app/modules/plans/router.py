from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.plans.models import MealPlan, PlanGoal, PlanType
from app.modules.plans.schemas import (
    MealPlanCreate,
    MealPlanResponse,
    MealPlanUpdate,
)
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/plans", tags=["Meal Plans"])


@router.post("/", response_model=MealPlanResponse)
def create_plan(
    payload: MealPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
        )
    ),
):
    plan = MealPlan(**payload.model_dump())

    db.add(plan)
    db.commit()
    db.refresh(plan)

    return plan


@router.get("/")
def list_plans(
    db: Session = Depends(get_db),
    search: str | None = Query(None),
    plan_type: PlanType | None = Query(None),
    goal: PlanGoal | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(MealPlan)

    if search:
        value = f"%{search}%"
        query = query.filter(
            or_(
                MealPlan.name_en.ilike(value),
                MealPlan.name_ar.ilike(value),
                MealPlan.description_en.ilike(value),
                MealPlan.description_ar.ilike(value),
            )
        )

    if plan_type:
        query = query.filter(MealPlan.plan_type == plan_type)

    if goal:
        query = query.filter(MealPlan.goal == goal)

    if is_active is not None:
        query = query.filter(MealPlan.is_active == is_active)

    total = query.count()

    plans = (
        query.order_by(MealPlan.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": plans,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/{plan_id}", response_model=MealPlanResponse)
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(MealPlan).filter(MealPlan.id == plan_id).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return plan


@router.put("/{plan_id}", response_model=MealPlanResponse)
def update_plan(
    plan_id: int,
    payload: MealPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
        )
    ),
):
    plan = db.query(MealPlan).filter(MealPlan.id == plan_id).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)

    db.commit()
    db.refresh(plan)

    return plan


@router.delete("/{plan_id}")
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)
    ),
):
    plan = db.query(MealPlan).filter(MealPlan.id == plan_id).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    db.delete(plan)
    db.commit()

    return {"message": "Plan deleted successfully"}