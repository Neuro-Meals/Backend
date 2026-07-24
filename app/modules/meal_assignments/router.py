from __future__ import annotations

from datetime import date, time
from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.modules.auth.dependencies import (
    get_current_user,
    require_roles,
)
from app.modules.meal_assignments.models import (
    MealAssignment,
    MealAssignmentItem,
)
from app.modules.meal_assignments.service import (
    build_assignment_response,
    create_or_update_assignments,
    get_assignment_by_id,
    get_category_or_404,
    get_delivery_preference_or_404,
    get_driver_or_404,
    update_assignment_meals,
)
from app.modules.users.models import User, UserRole


router = APIRouter(
    prefix="/meal-assignments",
    tags=["Meal Assignments"],
)

class MealAssignmentItemCreate(BaseModel):
    meal_id: int = Field(
        ...,
        gt=0,
        description="Meal to include in this category assignment",
    )

    quantity: int = Field(
        default=1,
        ge=1,
        le=20,
    )

    notes: str | None = Field(
        default=None,
        max_length=500,
    )


class MealCategoryAssignmentCreate(BaseModel):
    meal_category_id: int = Field(
        ...,
        gt=0,
    )

    delivery_preference_id: int = Field(
        ...,
        gt=0,
    )

    driver_id: int = Field(
        ...,
        gt=0,
    )

    delivery_time: time

    notes: str | None = Field(
        default=None,
        max_length=1000,
    )

    meals: list[MealAssignmentItemCreate] = Field(
        ...,
        min_length=1,
    )


class MealAssignmentBatchCreate(BaseModel):
    user_id: int = Field(
        ...,
        gt=0,
    )

    subscription_id: int = Field(
        ...,
        gt=0,
    )

    delivery_date: date

    assignments: list[MealCategoryAssignmentCreate] = Field(
        ...,
        min_length=1,
    )


class MealAssignmentUpdate(BaseModel):
    """
    All fields are optional.

    Only submitted fields will be changed.
    """

    delivery_preference_id: int | None = Field(
        default=None,
        gt=0,
    )

    driver_id: int | None = Field(
        default=None,
        gt=0,
    )

    delivery_time: time | None = None

    notes: str | None = Field(
        default=None,
        max_length=1000,
    )

    meals: list[MealAssignmentItemCreate] | None = Field(
        default=None,
        min_length=1,
    )

    is_active: bool | None = None

class MealAssignmentBatchResponse(BaseModel):
    message: str
    created_count: int
    updated_count: int
    total_count: int
    assignments: list[dict[str, Any]]


class MealAssignmentListResponse(BaseModel):
    items: list[dict[str, Any]]

    total: int
    page: int
    page_size: int
    total_pages: int

    has_next: bool
    has_previous: bool


class MessageResponse(BaseModel):
    message: str


class AssignmentStatisticsResponse(BaseModel):
    total_assignments: int
    active_assignments: int
    inactive_assignments: int
    total_meal_items: int
    total_portions: int

def model_to_dict(
    model: BaseModel,
) -> dict[str, Any]:
    """
    Convert Pydantic request models into dictionaries.

    This supports Pydantic v2 while retaining compatibility
    with older installations.
    """

    if hasattr(model, "model_dump"):
        return model.model_dump()

    return model.dict()


def normalize_role(
    value: Any,
) -> str | None:
    if value is None:
        return None

    if hasattr(value, "value"):
        value = value.value

    return str(value).strip().lower()


def current_user_role(
    current_user: User,
) -> str | None:
    return normalize_role(
        getattr(current_user, "role", None)
    )


def is_privileged_user(
    current_user: User,
) -> bool:
    privileged_roles = {
        normalize_role(UserRole.ADMIN),
        normalize_role(UserRole.SUPER_ADMIN),
        normalize_role(UserRole.NUTRITION_MANAGER),
        normalize_role(UserRole.DELIVERY_MANAGER),
    }

    return current_user_role(current_user) in privileged_roles


def is_driver(
    current_user: User,
) -> bool:
    return (
        current_user_role(current_user)
        == normalize_role(UserRole.DRIVER)
    )


def clean_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()

    return cleaned or None


def assignment_query(
    db: Session,
):
    """
    Base query containing relationships required by response
    serialization.
    """

    return (
        db.query(MealAssignment)
        .options(
            selectinload(MealAssignment.items).selectinload(
                MealAssignmentItem.meal
            ),
            selectinload(MealAssignment.category),
            selectinload(MealAssignment.customer),
            selectinload(MealAssignment.driver),
            selectinload(MealAssignment.assigned_by_user),
            selectinload(MealAssignment.subscription),
            selectinload(
                MealAssignment.delivery_preference
            ),
        )
    )


def ensure_assignment_access(
    assignment: MealAssignment,
    current_user: User,
) -> None:
    """
    Allow access when the user:

    - owns the assignment,
    - is its assigned driver, or
    - has a management role.
    """

    if is_privileged_user(current_user):
        return

    if assignment.user_id == current_user.id:
        return

    if (
        is_driver(current_user)
        and assignment.driver_id == current_user.id
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "You do not have permission to access "
            "this meal assignment"
        ),
    )


def ensure_assignment_management_access(
    current_user: User,
) -> None:
    """
    Only management roles may create, modify or deactivate
    meal assignments.
    """

    if is_privileged_user(current_user):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "You do not have permission to manage "
            "meal assignments"
        ),
    )


def serialize_assignments(
    db: Session,
    assignments: list[MealAssignment],
) -> list[dict[str, Any]]:
    return [
        build_assignment_response(
            db=db,
            assignment=assignment,
        )
        for assignment in assignments
    ]


def paginate_assignments(
    db: Session,
    query,
    page: int,
    page_size: int,
) -> MealAssignmentListResponse:
    """
    Execute a paginated assignment query.
    """

    total = query.order_by(None).count()
    total_pages = ceil(total / page_size) if total else 0

    assignments = (
        query.order_by(
            MealAssignment.delivery_date.asc(),
            MealAssignment.delivery_time.asc(),
            MealAssignment.id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return MealAssignmentListResponse(
        items=serialize_assignments(
            db=db,
            assignments=assignments,
        ),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@router.post(
    "",
    response_model=MealAssignmentBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_meal_assignments(
    payload: MealAssignmentBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or update meal assignments for one customer,
    subscription and delivery date.

    Each item under `assignments` represents one category,
    such as breakfast, lunch or dinner.
    """

    ensure_assignment_management_access(
        current_user=current_user,
    )

    assignment_data = [
        model_to_dict(item)
        for item in payload.assignments
    ]

    assignments, created_count, updated_count = (
        create_or_update_assignments(
            db=db,
            user_id=payload.user_id,
            subscription_id=payload.subscription_id,
            delivery_date=payload.delivery_date,
            assignment_items=assignment_data,
            assigned_by=current_user.id,
        )
    )

    serialized = serialize_assignments(
        db=db,
        assignments=assignments,
    )

    return MealAssignmentBatchResponse(
        message=(
            "Meal assignments saved successfully"
        ),
        created_count=created_count,
        updated_count=updated_count,
        total_count=len(serialized),
        assignments=serialized,
    )

@router.get(
    "/my",
    response_model=MealAssignmentListResponse,
)
def get_my_assignments(
    delivery_date_from: date | None = Query(
        default=None,
    ),
    delivery_date_to: date | None = Query(
        default=None,
    ),
    meal_category_id: int | None = Query(
        default=None,
        gt=0,
    ),
    active_only: bool = Query(
        default=True,
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return assignments belonging to the logged-in customer.
    """

    query = assignment_query(db).filter(
        MealAssignment.user_id == current_user.id,
    )

    if delivery_date_from is not None:
        query = query.filter(
            MealAssignment.delivery_date
            >= delivery_date_from,
        )

    if delivery_date_to is not None:
        query = query.filter(
            MealAssignment.delivery_date
            <= delivery_date_to,
        )

    if meal_category_id is not None:
        query = query.filter(
            MealAssignment.meal_category_id
            == meal_category_id,
        )

    if active_only:
        query = query.filter(
            MealAssignment.is_active.is_(True),
        )

    return paginate_assignments(
        db=db,
        query=query,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/my/date/{delivery_date}",
    response_model=list[dict[str, Any]],
)
def get_my_assignments_for_date(
    delivery_date: date,
    include_inactive: bool = Query(
        default=False,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the logged-in customer's assignments for one day.
    """

    query = assignment_query(db).filter(
        MealAssignment.user_id == current_user.id,
        MealAssignment.delivery_date == delivery_date,
    )

    if not include_inactive:
        query = query.filter(
            MealAssignment.is_active.is_(True),
        )

    assignments = (
        query.order_by(
            MealAssignment.delivery_time.asc(),
            MealAssignment.id.asc(),
        )
        .all()
    )

    return serialize_assignments(
        db=db,
        assignments=assignments,
    )

@router.get(
    "/driver/my",
    response_model=MealAssignmentListResponse,
)
def get_my_driver_assignments(
    delivery_date_from: date | None = Query(
        default=None,
    ),
    delivery_date_to: date | None = Query(
        default=None,
    ),
    meal_category_id: int | None = Query(
        default=None,
        gt=0,
    ),
    customer_id: int | None = Query(
        default=None,
        gt=0,
    ),
    active_only: bool = Query(
        default=True,
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return assignments allocated to the logged-in driver.

    Later, the driver dashboard should primarily use orders
    and deliveries. This route is useful before an order has
    been generated.
    """

    if not is_driver(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can access this endpoint",
        )

    query = assignment_query(db).filter(
        MealAssignment.driver_id == current_user.id,
    )

    if delivery_date_from is not None:
        query = query.filter(
            MealAssignment.delivery_date
            >= delivery_date_from,
        )

    if delivery_date_to is not None:
        query = query.filter(
            MealAssignment.delivery_date
            <= delivery_date_to,
        )

    if meal_category_id is not None:
        query = query.filter(
            MealAssignment.meal_category_id
            == meal_category_id,
        )

    if customer_id is not None:
        query = query.filter(
            MealAssignment.user_id == customer_id,
        )

    if active_only:
        query = query.filter(
            MealAssignment.is_active.is_(True),
        )

    return paginate_assignments(
        db=db,
        query=query,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/driver/{driver_id}",
    response_model=MealAssignmentListResponse,
)
def get_assignments_for_driver(
    driver_id: int,
    delivery_date_from: date | None = Query(
        default=None,
    ),
    delivery_date_to: date | None = Query(
        default=None,
    ),
    active_only: bool = Query(
        default=True,
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Management endpoint for viewing assignments allocated
    to a particular driver.
    """

    ensure_assignment_management_access(
        current_user=current_user,
    )

    get_driver_or_404(
        db=db,
        driver_id=driver_id,
    )

    query = assignment_query(db).filter(
        MealAssignment.driver_id == driver_id,
    )

    if delivery_date_from is not None:
        query = query.filter(
            MealAssignment.delivery_date
            >= delivery_date_from,
        )

    if delivery_date_to is not None:
        query = query.filter(
            MealAssignment.delivery_date
            <= delivery_date_to,
        )

    if active_only:
        query = query.filter(
            MealAssignment.is_active.is_(True),
        )

    return paginate_assignments(
        db=db,
        query=query,
        page=page,
        page_size=page_size,
    )

@router.get(
    "",
    response_model=MealAssignmentListResponse,
)
def list_meal_assignments(
    user_id: int | None = Query(
        default=None,
        gt=0,
    ),
    subscription_id: int | None = Query(
        default=None,
        gt=0,
    ),
    meal_category_id: int | None = Query(
        default=None,
        gt=0,
    ),
    driver_id: int | None = Query(
        default=None,
        gt=0,
    ),
    delivery_preference_id: int | None = Query(
        default=None,
        gt=0,
    ),
    delivery_date_from: date | None = Query(
        default=None,
    ),
    delivery_date_to: date | None = Query(
        default=None,
    ),
    is_active: bool | None = Query(
        default=None,
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all meal assignments with optional filters.
    """

    ensure_assignment_management_access(
        current_user=current_user,
    )

    if (
        delivery_date_from is not None
        and delivery_date_to is not None
        and delivery_date_from > delivery_date_to
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "delivery_date_from cannot be later than "
                "delivery_date_to"
            ),
        )

    query = assignment_query(db)

    if user_id is not None:
        query = query.filter(
            MealAssignment.user_id == user_id,
        )

    if subscription_id is not None:
        query = query.filter(
            MealAssignment.subscription_id
            == subscription_id,
        )

    if meal_category_id is not None:
        query = query.filter(
            MealAssignment.meal_category_id
            == meal_category_id,
        )

    if driver_id is not None:
        query = query.filter(
            MealAssignment.driver_id == driver_id,
        )

    if delivery_preference_id is not None:
        query = query.filter(
            MealAssignment.delivery_preference_id
            == delivery_preference_id,
        )

    if delivery_date_from is not None:
        query = query.filter(
            MealAssignment.delivery_date
            >= delivery_date_from,
        )

    if delivery_date_to is not None:
        query = query.filter(
            MealAssignment.delivery_date
            <= delivery_date_to,
        )

    if is_active is not None:
        query = query.filter(
            MealAssignment.is_active == is_active,
        )

    return paginate_assignments(
        db=db,
        query=query,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/date/{delivery_date}",
    response_model=list[dict[str, Any]],
)
def get_assignments_for_date(
    delivery_date: date,
    meal_category_id: int | None = Query(
        default=None,
        gt=0,
    ),
    driver_id: int | None = Query(
        default=None,
        gt=0,
    ),
    active_only: bool = Query(
        default=True,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Management endpoint for all assignments scheduled
    on a particular date.
    """

    ensure_assignment_management_access(
        current_user=current_user,
    )

    query = assignment_query(db).filter(
        MealAssignment.delivery_date == delivery_date,
    )

    if meal_category_id is not None:
        query = query.filter(
            MealAssignment.meal_category_id
            == meal_category_id,
        )

    if driver_id is not None:
        query = query.filter(
            MealAssignment.driver_id == driver_id,
        )

    if active_only:
        query = query.filter(
            MealAssignment.is_active.is_(True),
        )

    assignments = (
        query.order_by(
            MealAssignment.delivery_time.asc(),
            MealAssignment.meal_category_id.asc(),
            MealAssignment.id.asc(),
        )
        .all()
    )

    return serialize_assignments(
        db=db,
        assignments=assignments,
    )


@router.get(
    "/user/{user_id}",
    response_model=MealAssignmentListResponse,
)
def get_assignments_for_customer(
    user_id: int,
    subscription_id: int | None = Query(
        default=None,
        gt=0,
    ),
    delivery_date_from: date | None = Query(
        default=None,
    ),
    delivery_date_to: date | None = Query(
        default=None,
    ),
    active_only: bool = Query(
        default=True,
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Management endpoint for assignments belonging to one
    customer.
    """

    ensure_assignment_management_access(
        current_user=current_user,
    )

    query = assignment_query(db).filter(
        MealAssignment.user_id == user_id,
    )

    if subscription_id is not None:
        query = query.filter(
            MealAssignment.subscription_id
            == subscription_id,
        )

    if delivery_date_from is not None:
        query = query.filter(
            MealAssignment.delivery_date
            >= delivery_date_from,
        )

    if delivery_date_to is not None:
        query = query.filter(
            MealAssignment.delivery_date
            <= delivery_date_to,
        )

    if active_only:
        query = query.filter(
            MealAssignment.is_active.is_(True),
        )

    return paginate_assignments(
        db=db,
        query=query,
        page=page,
        page_size=page_size,
    )

@router.get(
    "/statistics/summary",
    response_model=AssignmentStatisticsResponse,
)
def get_assignment_statistics(
    delivery_date_from: date | None = Query(
        default=None,
    ),
    delivery_date_to: date | None = Query(
        default=None,
    ),
    driver_id: int | None = Query(
        default=None,
        gt=0,
    ),
    meal_category_id: int | None = Query(
        default=None,
        gt=0,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return assignment and portion totals for management
    dashboards.
    """

    ensure_assignment_management_access(
        current_user=current_user,
    )

    base_filters = []

    if delivery_date_from is not None:
        base_filters.append(
            MealAssignment.delivery_date
            >= delivery_date_from
        )

    if delivery_date_to is not None:
        base_filters.append(
            MealAssignment.delivery_date
            <= delivery_date_to
        )

    if driver_id is not None:
        base_filters.append(
            MealAssignment.driver_id == driver_id
        )

    if meal_category_id is not None:
        base_filters.append(
            MealAssignment.meal_category_id
            == meal_category_id
        )

    total_assignments = (
        db.query(func.count(MealAssignment.id))
        .filter(*base_filters)
        .scalar()
        or 0
    )

    active_assignments = (
        db.query(func.count(MealAssignment.id))
        .filter(
            *base_filters,
            MealAssignment.is_active.is_(True),
        )
        .scalar()
        or 0
    )

    inactive_assignments = (
        db.query(func.count(MealAssignment.id))
        .filter(
            *base_filters,
            MealAssignment.is_active.is_(False),
        )
        .scalar()
        or 0
    )

    item_query = (
        db.query(
            func.count(MealAssignmentItem.id),
            func.coalesce(
                func.sum(MealAssignmentItem.quantity),
                0,
            ),
        )
        .join(
            MealAssignment,
            MealAssignment.id
            == MealAssignmentItem.meal_assignment_id,
        )
        .filter(*base_filters)
    )

    total_meal_items, total_portions = (
        item_query.first()
    )

    return AssignmentStatisticsResponse(
        total_assignments=int(total_assignments),
        active_assignments=int(active_assignments),
        inactive_assignments=int(inactive_assignments),
        total_meal_items=int(total_meal_items or 0),
        total_portions=int(total_portions or 0),
    )

@router.get(
    "/{assignment_id}",
    response_model=dict[str, Any],
)
def get_meal_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return one assignment.
    """

    assignment = get_assignment_by_id(
        db=db,
        assignment_id=assignment_id,
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal assignment not found",
        )

    ensure_assignment_access(
        assignment=assignment,
        current_user=current_user,
    )

    return build_assignment_response(
        db=db,
        assignment=assignment,
    )


@router.patch(
    "/{assignment_id}",
    response_model=dict[str, Any],
)
def update_meal_assignment(
    assignment_id: int,
    payload: MealAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update one meal assignment.

    Submitted meals replace all existing meal items under
    the assignment.
    """

    ensure_assignment_management_access(
        current_user=current_user,
    )

    assignment = get_assignment_by_id(
        db=db,
        assignment_id=assignment_id,
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal assignment not found",
        )

    update_data = model_to_dict(payload)

    # Pydantic may include unset fields as None depending
    # on the version and method used. Determine explicitly
    # which fields were submitted.
    if hasattr(payload, "model_fields_set"):
        submitted_fields = payload.model_fields_set
    else:
        submitted_fields = payload.__fields_set__

    try:
        if "delivery_preference_id" in submitted_fields:
            if payload.delivery_preference_id is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        "delivery_preference_id cannot be null"
                    ),
                )

            get_delivery_preference_or_404(
                db=db,
                delivery_preference_id=(
                    payload.delivery_preference_id
                ),
                user_id=assignment.user_id,
                meal_category_id=(
                    assignment.meal_category_id
                ),
            )

            assignment.delivery_preference_id = (
                payload.delivery_preference_id
            )

        if "driver_id" in submitted_fields:
            if payload.driver_id is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail="driver_id cannot be null",
                )

            get_driver_or_404(
                db=db,
                driver_id=payload.driver_id,
            )

            assignment.driver_id = payload.driver_id

        if "delivery_time" in submitted_fields:
            if payload.delivery_time is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail="delivery_time cannot be null",
                )

            assignment.delivery_time = (
                payload.delivery_time
            )

        if "notes" in submitted_fields:
            assignment.notes = clean_optional_text(
                payload.notes
            )

        if "is_active" in submitted_fields:
            if payload.is_active is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail="is_active cannot be null",
                )

            assignment.is_active = payload.is_active

        assignment.assigned_by = current_user.id

        db.flush()

        if "meals" in submitted_fields:
            if payload.meals is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail="meals cannot be null",
                )

            meal_data = [
                model_to_dict(item)
                for item in payload.meals
            ]

            # This function commits and reloads the record.
            return build_assignment_response(
                db=db,
                assignment=update_assignment_meals(
                    db=db,
                    assignment=assignment,
                    meal_items=meal_data,
                ),
            )

        db.commit()

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise

    updated_assignment = get_assignment_by_id(
        db=db,
        assignment_id=assignment_id,
    )

    if updated_assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal assignment not found after update",
        )

    return build_assignment_response(
        db=db,
        assignment=updated_assignment,
    )


@router.delete(
    "/{assignment_id}",
    response_model=MessageResponse,
)
def deactivate_meal_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Soft-delete an assignment.

    The database row and its historical relationship to an
    order are preserved.
    """

    ensure_assignment_management_access(
        current_user=current_user,
    )

    assignment = get_assignment_by_id(
        db=db,
        assignment_id=assignment_id,
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal assignment not found",
        )

    if assignment.is_active is False:
        return MessageResponse(
            message="Meal assignment is already inactive",
        )

    assignment.is_active = False
    assignment.assigned_by = current_user.id

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    return MessageResponse(
        message="Meal assignment deactivated successfully",
    )


@router.post(
    "/{assignment_id}/restore",
    response_model=dict[str, Any],
)
def restore_meal_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Restore a previously deactivated assignment.
    """

    ensure_assignment_management_access(
        current_user=current_user,
    )

    assignment = get_assignment_by_id(
        db=db,
        assignment_id=assignment_id,
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal assignment not found",
        )

    assignment.is_active = True
    assignment.assigned_by = current_user.id

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    restored_assignment = get_assignment_by_id(
        db=db,
        assignment_id=assignment_id,
    )

    if restored_assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal assignment not found after restoration",
        )

    return build_assignment_response(
        db=db,
        assignment=restored_assignment,
    )