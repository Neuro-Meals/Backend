from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import (
    get_current_user,
    require_roles,
)
from app.modules.meal_assignments.models import (
    MealAssignment,
)
from app.modules.meal_assignments.schemas import (
    KitchenDailyResponse,
    MealAssignmentBatchCreate,
    MealAssignmentBatchResponse,
    MealAssignmentDeleteResponse,
    MealAssignmentListResponse,
    MealAssignmentResponse,
    MealAssignmentUpdate,
)
from app.modules.meal_assignments.service import (
    build_assignment_response,
    clean_optional_text,
    create_or_update_assignments,
    get_assignment_by_id,
    get_meal_or_404,
    validate_meal_matches_category,
)
from app.modules.meals.models import Meal, MealCategory
from app.modules.users.models import User, UserRole


router = APIRouter(
    prefix="/meal-assignments",
    tags=["Meal Assignments"],
)


STAFF_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.NUTRITION_MANAGER,
)

@router.post(
    "",
    response_model=MealAssignmentBatchResponse,
)
def assign_customer_meals(
    payload: MealAssignmentBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*STAFF_ROLES)
    ),
):
    assignments_data = [
        assignment.model_dump()
        for assignment in payload.assignments
    ]

    try:
        (
            assignments,
            created_count,
            updated_count,
        ) = create_or_update_assignments(
            db=db,
            user_id=payload.user_id,
            subscription_id=payload.subscription_id,
            delivery_date=payload.delivery_date,
            assignment_items=assignments_data,
            assigned_by=current_user.id,
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise

    response_data = [
        build_assignment_response(
            db=db,
            assignment=assignment,
        )
        for assignment in assignments
    ]

    return {
        "success": True,
        "message": "Customer meals assigned successfully",
        "created_count": created_count,
        "updated_count": updated_count,
        "delivery_date": payload.delivery_date,
        "user_id": payload.user_id,
        "subscription_id": payload.subscription_id,
        "data": response_data,
    }

@router.get(
    "/my",
    response_model=MealAssignmentListResponse,
)
def get_my_assignments(
    start_date: date | None = Query(
        default=None,
    ),
    end_date: date | None = Query(
        default=None,
    ),
    is_active: bool | None = Query(
        default=True,
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(MealAssignment)
        .filter(
            MealAssignment.user_id
            == current_user.id
        )
    )

    if start_date is not None:
        query = query.filter(
            MealAssignment.delivery_date
            >= start_date
        )

    if end_date is not None:
        query = query.filter(
            MealAssignment.delivery_date
            <= end_date
        )

    if is_active is not None:
        query = query.filter(
            MealAssignment.is_active
            == is_active
        )

    total = query.count()

    assignments = (
        query.order_by(
            MealAssignment.delivery_date.asc(),
            MealAssignment.meal_category_id.asc(),
        )
        .offset(
            (page - 1) * limit
        )
        .limit(limit)
        .all()
    )

    data = [
        build_assignment_response(
            db=db,
            assignment=assignment,
        )
        for assignment in assignments
    ]

    return {
        "data": data,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (
            (total + limit - 1) // limit
        ),
    }

@router.get(
    "/my/date/{target_date}",
    response_model=list[MealAssignmentResponse],
)
def get_my_assignments_for_date(
    target_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignments = (
        db.query(MealAssignment)
        .filter(
            MealAssignment.user_id
            == current_user.id,
            MealAssignment.delivery_date
            == target_date,
            MealAssignment.is_active.is_(True),
        )
        .order_by(
            MealAssignment.meal_category_id.asc()
        )
        .all()
    )

    return [
        build_assignment_response(
            db=db,
            assignment=assignment,
        )
        for assignment in assignments
    ]

@router.get(
    "/user/{user_id}",
    response_model=MealAssignmentListResponse,
)
def get_user_assignments(
    user_id: int,
    start_date: date | None = Query(
        default=None,
    ),
    end_date: date | None = Query(
        default=None,
    ),
    subscription_id: int | None = Query(
        default=None,
    ),
    is_active: bool | None = Query(
        default=True,
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*STAFF_ROLES)
    ),
):
    query = (
        db.query(MealAssignment)
        .filter(
            MealAssignment.user_id == user_id
        )
    )

    if start_date is not None:
        query = query.filter(
            MealAssignment.delivery_date
            >= start_date
        )

    if end_date is not None:
        query = query.filter(
            MealAssignment.delivery_date
            <= end_date
        )

    if subscription_id is not None:
        query = query.filter(
            MealAssignment.subscription_id
            == subscription_id
        )

    if is_active is not None:
        query = query.filter(
            MealAssignment.is_active
            == is_active
        )

    total = query.count()

    assignments = (
        query.order_by(
            MealAssignment.delivery_date.asc(),
            MealAssignment.meal_category_id.asc(),
        )
        .offset(
            (page - 1) * limit
        )
        .limit(limit)
        .all()
    )

    return {
        "data": [
            build_assignment_response(
                db=db,
                assignment=assignment,
            )
            for assignment in assignments
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (
            (total + limit - 1) // limit
        ),
    }

@router.get(
    "/date/{target_date}",
    response_model=KitchenDailyResponse,
)
def get_daily_assignments(
    target_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
            UserRole.CHEF,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    assignments = (
        db.query(MealAssignment)
        .filter(
            MealAssignment.delivery_date
            == target_date,
            MealAssignment.is_active.is_(True),
        )
        .order_by(
            MealAssignment.meal_category_id.asc(),
            MealAssignment.meal_id.asc(),
            MealAssignment.user_id.asc(),
        )
        .all()
    )

    assignment_data = [
        build_assignment_response(
            db=db,
            assignment=assignment,
        )
        for assignment in assignments
    ]

    meal_totals = (
        db.query(
            MealAssignment.meal_id,
            MealAssignment.meal_category_id,
            func.sum(
                MealAssignment.quantity
            ).label("total_quantity"),
            func.count(
                func.distinct(
                    MealAssignment.user_id
                )
            ).label("customer_count"),
        )
        .filter(
            MealAssignment.delivery_date
            == target_date,
            MealAssignment.is_active.is_(True),
        )
        .group_by(
            MealAssignment.meal_id,
            MealAssignment.meal_category_id,
        )
        .order_by(
            MealAssignment.meal_category_id.asc(),
            MealAssignment.meal_id.asc(),
        )
        .all()
    )

    meals = []

    for row in meal_totals:
        meal = (
            db.query(Meal)
            .filter(
                Meal.id == row.meal_id
            )
            .first()
        )

        category = (
            db.query(MealCategory)
            .filter(
                MealCategory.id
                == row.meal_category_id
            )
            .first()
        )

        meals.append(
            {
                "meal_id": row.meal_id,
                "meal_name": (
                    meal.name_en
                    if meal
                    else "Unknown meal"
                ),
                "meal_name_ar": (
                    meal.name_ar
                    if meal
                    else None
                ),
                "meal_category_id": (
                    row.meal_category_id
                ),
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
                "total_quantity": int(
                    row.total_quantity or 0
                ),
                "customer_count": int(
                    row.customer_count or 0
                ),
            }
        )

    unique_customer_ids = {
        assignment.user_id
        for assignment in assignments
    }

    total_meal_quantity = sum(
        assignment.quantity
        for assignment in assignments
    )

    return {
        "delivery_date": target_date,
        "total_assignments": len(assignments),
        "total_customers": len(
            unique_customer_ids
        ),
        "total_meal_quantity": (
            total_meal_quantity
        ),
        "meals": meals,
        "assignments": assignment_data,
    }

@router.get(
    "/{assignment_id}",
    response_model=MealAssignmentResponse,
)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*STAFF_ROLES)
    ),
):
    assignment = get_assignment_by_id(
        db=db,
        assignment_id=assignment_id,
    )

    if assignment is None:
        raise HTTPException(
            status_code=404,
            detail="Meal assignment not found",
        )

    return build_assignment_response(
        db=db,
        assignment=assignment,
    )

@router.patch(
    "/{assignment_id}",
    response_model=MealAssignmentResponse,
)
def update_assignment(
    assignment_id: int,
    payload: MealAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*STAFF_ROLES)
    ),
):
    assignment = get_assignment_by_id(
        db=db,
        assignment_id=assignment_id,
    )

    if assignment is None:
        raise HTTPException(
            status_code=404,
            detail="Meal assignment not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True,
    )

    if "meal_id" in update_data:
        meal = get_meal_or_404(
            db=db,
            meal_id=update_data["meal_id"],
        )

        validate_meal_matches_category(
            meal=meal,
            category_id=(
                assignment.meal_category_id
            ),
        )

        assignment.meal_id = meal.id

    if "quantity" in update_data:
        assignment.quantity = update_data[
            "quantity"
        ]

    if "notes" in update_data:
        assignment.notes = clean_optional_text(
            update_data["notes"]
        )

    if "is_active" in update_data:
        assignment.is_active = update_data[
            "is_active"
        ]

    assignment.assigned_by = current_user.id

    db.commit()
    db.refresh(assignment)

    return build_assignment_response(
        db=db,
        assignment=assignment,
    )

@router.delete(
    "/{assignment_id}",
    response_model=MealAssignmentDeleteResponse,
)
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*STAFF_ROLES)
    ),
):
    assignment = get_assignment_by_id(
        db=db,
        assignment_id=assignment_id,
    )

    if assignment is None:
        raise HTTPException(
            status_code=404,
            detail="Meal assignment not found",
        )

    assignment.is_active = False
    assignment.assigned_by = current_user.id

    db.commit()

    return {
        "success": True,
        "message": "Meal assignment deactivated successfully",
    }