from collections import defaultdict

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import (
    get_current_user,
    require_roles,
)
from app.modules.meals.models import Meal, MealCategory
from app.modules.plan_menus.models import (
    PlanMenuItem,
    WeekDay,
)
from app.modules.plan_menus.schemas import (
    PlanMenuItemCreate,
    PlanMenuItemResponse,
    PlanMenuItemUpdate,
)
from app.modules.plans.models import MealPlan
from app.modules.users.models import User, UserRole


router = APIRouter(
    prefix="/plan-menus",
    tags=["Plan Weekly Menus"],
)


def enum_value(value):
    if value is None:
        return None

    return value.value if hasattr(value, "value") else value


def get_menu_item_or_404(
    db: Session,
    menu_item_id: int,
) -> PlanMenuItem:
    menu_item = (
        db.query(PlanMenuItem)
        .filter(PlanMenuItem.id == menu_item_id)
        .first()
    )

    if menu_item is None:
        raise HTTPException(
            status_code=404,
            detail="Plan menu item not found",
        )

    return menu_item


def build_menu_item_payload(
    db: Session,
    menu_item: PlanMenuItem,
) -> dict:
    meal = (
        db.query(Meal)
        .filter(Meal.id == menu_item.meal_id)
        .first()
    )

    category = (
        db.query(MealCategory)
        .filter(
            MealCategory.id == menu_item.category_id
        )
        .first()
    )

    return {
        "id": menu_item.id,
        "plan_id": menu_item.plan_id,
        "meal_id": menu_item.meal_id,
        "category_id": menu_item.category_id,
        "day_of_week": enum_value(
            menu_item.day_of_week
        ),
        "quantity": menu_item.quantity,
        "sort_order": menu_item.sort_order,
        "is_active": menu_item.is_active,
        "created_at": menu_item.created_at,
        "updated_at": menu_item.updated_at,

        "meal": {
            "id": meal.id,
            "name_en": meal.name_en,
            "name_ar": meal.name_ar,
            "image_url": meal.image_url,
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
            ),
            "allergens": getattr(
                meal,
                "allergens",
                None,
            ),
        }
        if meal
        else None,

        "category": {
            "id": category.id,
            "name_en": category.name_en,
            "name_ar": category.name_ar,
        }
        if category
        else None,
    }


@router.post(
    "/",
    response_model=PlanMenuItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_plan_menu_item(
    payload: PlanMenuItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
        )
    ),
):
    plan = (
        db.query(MealPlan)
        .filter(MealPlan.id == payload.plan_id)
        .first()
    )

    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="Plan not found",
        )

    meal = (
        db.query(Meal)
        .filter(Meal.id == payload.meal_id)
        .first()
    )

    if meal is None:
        raise HTTPException(
            status_code=404,
            detail="Meal not found",
        )

    category = (
        db.query(MealCategory)
        .filter(
            MealCategory.id == payload.category_id
        )
        .first()
    )

    if category is None:
        raise HTTPException(
            status_code=404,
            detail="Meal category not found",
        )

    # Ensure the selected meal belongs to the selected category.
    if meal.category_id != category.id:
        raise HTTPException(
            status_code=400,
            detail=(
                "The selected meal does not belong "
                "to the selected category"
            ),
        )

    menu_item = PlanMenuItem(
        plan_id=payload.plan_id,
        meal_id=payload.meal_id,
        category_id=payload.category_id,
        day_of_week=payload.day_of_week,
        quantity=payload.quantity,
        sort_order=payload.sort_order,
        is_active=True,
    )

    db.add(menu_item)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=(
                "This meal is already assigned to this "
                "plan, day and category"
            ),
        ) from exc

    db.refresh(menu_item)

    return build_menu_item_payload(
        db,
        menu_item,
    )


@router.get(
    "/plan/{plan_id}/weekly",
)
def get_plan_weekly_menu(
    plan_id: int,
    db: Session = Depends(get_db),
):
    plan = (
        db.query(MealPlan)
        .filter(MealPlan.id == plan_id)
        .first()
    )

    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="Plan not found",
        )

    menu_items = (
        db.query(PlanMenuItem)
        .filter(
            PlanMenuItem.plan_id == plan_id,
            PlanMenuItem.is_active.is_(True),
        )
        .order_by(
            PlanMenuItem.day_of_week.asc(),
            PlanMenuItem.sort_order.asc(),
            PlanMenuItem.id.asc(),
        )
        .all()
    )

    grouped: dict[str, dict[str, list]] = defaultdict(
        lambda: defaultdict(list)
    )

    for menu_item in menu_items:
        item = build_menu_item_payload(
            db,
            menu_item,
        )

        day = enum_value(menu_item.day_of_week)

        category_name = (
            item["category"]["name_en"]
            if item["category"]
            else "Uncategorized"
        )

        grouped[day][category_name].append(
            item
        )

    day_order = [
        WeekDay.MONDAY.value,
        WeekDay.TUESDAY.value,
        WeekDay.WEDNESDAY.value,
        WeekDay.THURSDAY.value,
        WeekDay.FRIDAY.value,
        WeekDay.SATURDAY.value,
        WeekDay.SUNDAY.value,
    ]

    days = []

    for day in day_order:
        categories = []

        for category_name, items in grouped[
            day
        ].items():
            categories.append(
                {
                    "category_name": category_name,
                    "items": items,
                }
            )

        days.append(
            {
                "day_of_week": day,
                "categories": categories,
            }
        )

    return {
        "plan_id": plan.id,
        "plan_name": plan.name_en,
        "days": days,
    }


@router.get(
    "/plan/{plan_id}",
)
def list_plan_menu_items(
    plan_id: int,
    db: Session = Depends(get_db),
    day_of_week: WeekDay | None = Query(None),
    category_id: int | None = Query(None),
):
    query = db.query(PlanMenuItem).filter(
        PlanMenuItem.plan_id == plan_id
    )

    if day_of_week is not None:
        query = query.filter(
            PlanMenuItem.day_of_week == day_of_week
        )

    if category_id is not None:
        query = query.filter(
            PlanMenuItem.category_id == category_id
        )

    menu_items = (
        query.order_by(
            PlanMenuItem.day_of_week.asc(),
            PlanMenuItem.sort_order.asc(),
        )
        .all()
    )

    return {
        "plan_id": plan_id,
        "total": len(menu_items),
        "data": [
            build_menu_item_payload(
                db,
                menu_item,
            )
            for menu_item in menu_items
        ],
    }


@router.patch(
    "/{menu_item_id}",
    response_model=PlanMenuItemResponse,
)
def update_plan_menu_item(
    menu_item_id: int,
    payload: PlanMenuItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
        )
    ),
):
    menu_item = get_menu_item_or_404(
        db,
        menu_item_id,
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    if "meal_id" in update_data:
        meal = (
            db.query(Meal)
            .filter(
                Meal.id == update_data["meal_id"]
            )
            .first()
        )

        if meal is None:
            raise HTTPException(
                status_code=404,
                detail="Meal not found",
            )

    if "category_id" in update_data:
        category = (
            db.query(MealCategory)
            .filter(
                MealCategory.id
                == update_data["category_id"]
            )
            .first()
        )

        if category is None:
            raise HTTPException(
                status_code=404,
                detail="Meal category not found",
            )

    for field, value in update_data.items():
        setattr(
            menu_item,
            field,
            value,
        )

    selected_meal = (
        db.query(Meal)
        .filter(Meal.id == menu_item.meal_id)
        .first()
    )

    if (
        selected_meal
        and selected_meal.category_id
        != menu_item.category_id
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "The selected meal does not belong "
                "to the selected category"
            ),
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Duplicate plan menu item",
        ) from exc

    db.refresh(menu_item)

    return build_menu_item_payload(
        db,
        menu_item,
    )


@router.delete(
    "/{menu_item_id}",
)
def delete_plan_menu_item(
    menu_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
        )
    ),
):
    menu_item = get_menu_item_or_404(
        db,
        menu_item_id,
    )

    db.delete(menu_item)
    db.commit()

    return {
        "message": "Plan menu item deleted successfully"
    }