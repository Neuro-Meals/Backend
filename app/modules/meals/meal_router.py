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

    # Build response with category info included
    category_ids = {m.category_id for m in meals}
    categories = (
        db.query(MealCategory)
        .filter(MealCategory.id.in_(category_ids))
        .all()
        if category_ids else []
    )
    cat_map = {c.id: c for c in categories}

    data = []
    for m in meals:
        cat = cat_map.get(m.category_id)
        data.append({
            "id": m.id,
            "category_id": m.category_id,
            "category_name": cat.name_en if cat else None,
            "category": {
                "id": cat.id,
                "name_en": cat.name_en,
                "name_ar": cat.name_ar,
            } if cat else None,
            "name_en": m.name_en,
            "name_ar": m.name_ar,
            "description_en": m.description_en,
            "description_ar": m.description_ar,
            "calories": m.calories,
            "protein_g": m.protein_g,
            "carbs_g": m.carbs_g,
            "fat_g": m.fat_g,
            "fiber_g": m.fiber_g,
            "sugar_g": m.sugar_g,
            "sodium_mg": m.sodium_mg,
            "price": m.price,
            "image_url": m.image_url,
            "ingredients": m.ingredients,
            "allergens": m.allergens,
            "diet_tags": m.diet_tags,
            "is_available": m.is_available,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    return {
        "data": data,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/{meal_id}")
def get_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    cat = db.query(MealCategory).filter(MealCategory.id == meal.category_id).first()

    return {
        "id": meal.id,
        "category_id": meal.category_id,
        "category_name": cat.name_en if cat else None,
        "category": {
            "id": cat.id,
            "name_en": cat.name_en,
            "name_ar": cat.name_ar,
        } if cat else None,
        "name_en": meal.name_en,
        "name_ar": meal.name_ar,
        "description_en": meal.description_en,
        "description_ar": meal.description_ar,
        "calories": meal.calories,
        "protein_g": meal.protein_g,
        "carbs_g": meal.carbs_g,
        "fat_g": meal.fat_g,
        "fiber_g": meal.fiber_g,
        "sugar_g": meal.sugar_g,
        "sodium_mg": meal.sodium_mg,
        "price": meal.price,
        "image_url": meal.image_url,
        "ingredients": meal.ingredients,
        "allergens": meal.allergens,
        "diet_tags": meal.diet_tags,
        "is_available": meal.is_available,
        "created_at": meal.created_at.isoformat() if meal.created_at else None,
    }


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