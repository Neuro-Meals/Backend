from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.users.models import User, UserRole
from app.modules.meals.models import Meal, MealCategory
from app.modules.meals.schemas import MealCreate, MealUpdate, MealResponse


router = APIRouter(prefix="/meals", tags=["Meals"])


@router.post("/", response_model=MealResponse)
def create_meal(
    payload: MealCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
        )
    ),
):
    category = db.query(MealCategory).filter(MealCategory.id == payload.category_id).first()

    if not category:
        raise HTTPException(status_code=404, detail="Meal category not found")

    meal = Meal(**payload.model_dump())

    db.add(meal)
    db.commit()
    db.refresh(meal)

    return meal


@router.get("/")
def list_meals(
    db: Session = Depends(get_db),
    search: str | None = Query(None),
    category_id: int | None = Query(None),
    min_calories: float | None = Query(None),
    max_calories: float | None = Query(None),
    diet_tag: str | None = Query(None),
    is_available: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Meal)

    if search:
        value = f"%{search}%"
        query = query.filter(
            or_(
                Meal.name_en.ilike(value),
                Meal.name_ar.ilike(value),
                Meal.description_en.ilike(value),
                Meal.description_ar.ilike(value),
            )
        )

    if category_id:
        query = query.filter(Meal.category_id == category_id)

    if min_calories is not None:
        query = query.filter(Meal.calories >= min_calories)

    if max_calories is not None:
        query = query.filter(Meal.calories <= max_calories)

    if diet_tag:
        query = query.filter(Meal.diet_tags.contains([diet_tag]))

    if is_available is not None:
        query = query.filter(Meal.is_available == is_available)

    total = query.count()

    meals = (
        query.order_by(Meal.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": meals,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/{meal_id}", response_model=MealResponse)
def get_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    return meal


@router.put("/{meal_id}", response_model=MealResponse)
def update_meal(
    meal_id: int,
    payload: MealUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
        )
    ),
):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "category_id" in update_data:
        category = db.query(MealCategory).filter(
            MealCategory.id == update_data["category_id"]
        ).first()

        if not category:
            raise HTTPException(status_code=404, detail="Meal category not found")

    for field, value in update_data.items():
        setattr(meal, field, value)

    db.commit()
    db.refresh(meal)

    return meal


@router.delete("/{meal_id}")
def delete_meal(
    meal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)
    ),
):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    db.delete(meal)
    db.commit()

    return {"message": "Meal deleted successfully"}