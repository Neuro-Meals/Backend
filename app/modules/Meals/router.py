from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.users.models import User, UserRole
from app.modules.meals.models import MealCategory
from app.modules.meals.schemas import (
    MealCategoryCreate,
    MealCategoryUpdate,
    MealCategoryResponse,
)


router = APIRouter(prefix="/meal-categories", tags=["Meal Categories"])


@router.post("/", response_model=MealCategoryResponse)
def create_category(
    payload: MealCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.NUTRITION_MANAGER)),
):
    exists = db.query(MealCategory).filter(MealCategory.name_en == payload.name_en).first()
    if exists:
        raise HTTPException(status_code=400, detail="Category already exists")

    category = MealCategory(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)

    return category


@router.get("/")
def list_categories(
    db: Session = Depends(get_db),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(MealCategory)

    if search:
        value = f"%{search}%"
        query = query.filter(
            or_(
                MealCategory.name_en.ilike(value),
                MealCategory.name_ar.ilike(value),
                MealCategory.description.ilike(value),
            )
        )

    if is_active is not None:
        query = query.filter(MealCategory.is_active == is_active)

    total = query.count()

    categories = (
        query.order_by(MealCategory.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": categories,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/{category_id}", response_model=MealCategoryResponse)
def get_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(MealCategory).filter(MealCategory.id == category_id).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    return category


@router.put("/{category_id}", response_model=MealCategoryResponse)
def update_category(
    category_id: int,
    payload: MealCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.NUTRITION_MANAGER)),
):
    category = db.query(MealCategory).filter(MealCategory.id == category_id).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)

    return category


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
):
    category = db.query(MealCategory).filter(MealCategory.id == category_id).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db.delete(category)
    db.commit()

    return {"message": "Category deleted successfully"}