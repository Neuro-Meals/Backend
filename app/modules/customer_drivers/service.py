from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.modules.customer_drivers.models import CustomerDriverAssignment
from app.modules.customer_drivers.schemas import (
    CustomerDriverAssignRequest,
    CustomerDriverUpdateRequest,
)
from app.modules.users.models import User, UserRole

def utc_now() -> datetime:
    """
    Return the current UTC datetime.
    """

    return datetime.now(timezone.utc)


def enum_value(value) -> str | None:
    """
    Return the normalized string value of an enum or string.

    Examples:
        UserRole.DRIVER -> "driver"
        "DRIVER" -> "driver"
    """

    if value is None:
        return None

    raw_value = getattr(value, "value", value)

    return str(raw_value).strip().lower()


def get_user_role(user: User) -> str | None:
    """
    Extract the user's role in a normalized format.
    """

    return enum_value(getattr(user, "role", None))


def build_assignment_query():
    """
    Base query that loads all assignment relationships.
    """

    return select(CustomerDriverAssignment).options(
        joinedload(CustomerDriverAssignment.customer),
        joinedload(CustomerDriverAssignment.driver),
        joinedload(CustomerDriverAssignment.assigned_by_user),
    )

def get_user_by_id(
    db: Session,
    user_id: int,
) -> User:
    """
    Find a user by ID or raise a 404 response.
    """

    user = db.scalar(
        select(User).where(User.id == user_id)
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return user


def validate_customer(
    db: Session,
    customer_id: int,
) -> User:
    """
    Ensure the selected user exists and has the customer role.
    """

    customer = get_user_by_id(
        db=db,
        user_id=customer_id,
    )

    customer_role = get_user_role(customer)
    expected_role = enum_value(UserRole.CUSTOMER)

    if customer_role != expected_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected user is not a customer.",
        )

    if getattr(customer, "is_active", True) is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected customer account is inactive.",
        )

    return customer


def validate_driver(
    db: Session,
    driver_id: int,
) -> User:
    """
    Ensure the selected user exists and has the driver role.
    """

    driver = get_user_by_id(
        db=db,
        user_id=driver_id,
    )

    driver_role = get_user_role(driver)
    expected_role = enum_value(UserRole.DRIVER)

    if driver_role != expected_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected user is not a driver.",
        )

    if getattr(driver, "is_active", True) is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected driver account is inactive.",
        )

    return driver

def get_assignment_by_id(
    db: Session,
    assignment_id: int,
) -> CustomerDriverAssignment:
    """
    Return one customer-driver assignment by ID.
    """

    assignment = db.scalar(
        build_assignment_query().where(
            CustomerDriverAssignment.id == assignment_id
        )
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer-driver assignment not found.",
        )

    return assignment


def get_active_assignment_for_customer(
    db: Session,
    customer_id: int,
    raise_if_missing: bool = True,
) -> CustomerDriverAssignment | None:
    """
    Return the customer's current active driver assignment.
    """

    assignment = db.scalar(
        build_assignment_query().where(
            CustomerDriverAssignment.customer_id == customer_id,
            CustomerDriverAssignment.is_active.is_(True),
        )
    )

    if assignment is None and raise_if_missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This customer does not have an active driver assignment.",
        )

    return assignment


def get_customer_assignment_history(
    db: Session,
    customer_id: int,
) -> list[CustomerDriverAssignment]:
    """
    Return all current and previous driver assignments for a customer.
    """

    validate_customer(
        db=db,
        customer_id=customer_id,
    )

    assignments = db.scalars(
        build_assignment_query()
        .where(
            CustomerDriverAssignment.customer_id == customer_id
        )
        .order_by(
            CustomerDriverAssignment.assigned_at.desc(),
            CustomerDriverAssignment.id.desc(),
        )
    ).unique().all()

    return list(assignments)

def assign_driver_to_customer(
    db: Session,
    payload: CustomerDriverAssignRequest,
    assigned_by_user: User,
) -> CustomerDriverAssignment:
    """
    Assign a dedicated driver to a customer.

    A customer can have only one active driver. If the customer already has
    an active driver, the frontend should use the change-driver endpoint.
    """

    customer = validate_customer(
        db=db,
        customer_id=payload.customer_id,
    )

    driver = validate_driver(
        db=db,
        driver_id=payload.driver_id,
    )

    if customer.id == driver.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A customer cannot be assigned as their own driver.",
        )

    existing_assignment = get_active_assignment_for_customer(
        db=db,
        customer_id=customer.id,
        raise_if_missing=False,
    )

    if existing_assignment is not None:
        if existing_assignment.driver_id == driver.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This driver is already assigned to the customer.",
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This customer already has an active driver. "
                "Use the change-driver endpoint to replace the current driver."
            ),
        )

    assignment = CustomerDriverAssignment(
        customer_id=customer.id,
        driver_id=driver.id,
        assigned_by=assigned_by_user.id,
        assignment_reason=payload.assignment_reason,
        notes=payload.notes,
        is_active=True,
        assigned_at=utc_now(),
    )

    db.add(assignment)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The customer already has an active driver assignment.",
        ) from exc

    return get_assignment_by_id(
        db=db,
        assignment_id=assignment.id,
    )

def change_customer_driver(
    db: Session,
    customer_id: int,
    payload: CustomerDriverUpdateRequest,
    assigned_by_user: User,
) -> CustomerDriverAssignment:
    """
    Replace the customer's current driver while preserving assignment history.

    The old assignment becomes inactive, and a new active assignment is
    created for the selected driver.
    """

    customer = validate_customer(
        db=db,
        customer_id=customer_id,
    )

    new_driver = validate_driver(
        db=db,
        driver_id=payload.driver_id,
    )

    if customer.id == new_driver.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A customer cannot be assigned as their own driver.",
        )

    current_assignment = get_active_assignment_for_customer(
        db=db,
        customer_id=customer.id,
        raise_if_missing=True,
    )

    if current_assignment.driver_id == new_driver.id:
        current_assignment.assignment_reason = payload.assignment_reason
        current_assignment.notes = payload.notes
        current_assignment.updated_at = utc_now()

        db.add(current_assignment)
        db.commit()

        return get_assignment_by_id(
            db=db,
            assignment_id=current_assignment.id,
        )

    current_time = utc_now()

    current_assignment.is_active = False
    current_assignment.ended_at = current_time
    current_assignment.updated_at = current_time

    new_assignment = CustomerDriverAssignment(
        customer_id=customer.id,
        driver_id=new_driver.id,
        assigned_by=assigned_by_user.id,
        assignment_reason=payload.assignment_reason,
        notes=payload.notes,
        is_active=True,
        assigned_at=current_time,
    )

    db.add(current_assignment)
    db.add(new_assignment)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to change the driver because an active assignment exists.",
        ) from exc

    return get_assignment_by_id(
        db=db,
        assignment_id=new_assignment.id,
    )

def deactivate_customer_driver(
    db: Session,
    customer_id: int,
) -> CustomerDriverAssignment:
    """
    Remove the customer's current dedicated driver without deleting history.
    """

    validate_customer(
        db=db,
        customer_id=customer_id,
    )

    assignment = get_active_assignment_for_customer(
        db=db,
        customer_id=customer_id,
        raise_if_missing=True,
    )

    current_time = utc_now()

    assignment.is_active = False
    assignment.ended_at = current_time
    assignment.updated_at = current_time

    db.add(assignment)
    db.commit()

    return get_assignment_by_id(
        db=db,
        assignment_id=assignment.id,
    )

def list_customer_driver_assignments(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    active_only: bool = True,
    search: str | None = None,
) -> tuple[int, list[CustomerDriverAssignment]]:
    """
    Return paginated customer-driver assignments for the admin dashboard.
    """

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size

    filters = []

    if active_only:
        filters.append(
            CustomerDriverAssignment.is_active.is_(True)
        )

    if search:
        normalized_search = f"%{search.strip()}%"

        filters.append(
            CustomerDriverAssignment.customer.has(
                (User.first_name.ilike(normalized_search))
                | (User.last_name.ilike(normalized_search))
                | (User.email.ilike(normalized_search))
                | (User.phone.ilike(normalized_search))
            )
            |
            CustomerDriverAssignment.driver.has(
                (User.first_name.ilike(normalized_search))
                | (User.last_name.ilike(normalized_search))
                | (User.email.ilike(normalized_search))
                | (User.phone.ilike(normalized_search))
            )
        )

    count_statement = select(
        func.count(CustomerDriverAssignment.id)
    )

    assignments_statement = build_assignment_query()

    if filters:
        count_statement = count_statement.where(*filters)
        assignments_statement = assignments_statement.where(*filters)

    total = db.scalar(count_statement) or 0

    assignments = db.scalars(
        assignments_statement
        .order_by(
            CustomerDriverAssignment.is_active.desc(),
            CustomerDriverAssignment.assigned_at.desc(),
            CustomerDriverAssignment.id.desc(),
        )
        .offset(offset)
        .limit(page_size)
    ).unique().all()

    return total, list(assignments)


def list_driver_customers(
    db: Session,
    driver_id: int,
    active_only: bool = True,
) -> list[CustomerDriverAssignment]:
    """
    Return all customers assigned to a particular driver.
    """

    validate_driver(
        db=db,
        driver_id=driver_id,
    )

    statement = build_assignment_query().where(
        CustomerDriverAssignment.driver_id == driver_id
    )

    if active_only:
        statement = statement.where(
            CustomerDriverAssignment.is_active.is_(True)
        )

    assignments = db.scalars(
        statement.order_by(
            CustomerDriverAssignment.assigned_at.desc(),
            CustomerDriverAssignment.id.desc(),
        )
    ).unique().all()

    return list(assignments)


def list_current_driver_customers(
    db: Session,
    current_driver: User,
) -> list[CustomerDriverAssignment]:
    """
    Return customers assigned to the currently authenticated driver.
    """

    expected_driver_role = enum_value(UserRole.DRIVER)
    current_role = get_user_role(current_driver)

    if current_role != expected_driver_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can access their assigned customers.",
        )

    assignments = db.scalars(
        build_assignment_query()
        .where(
            CustomerDriverAssignment.driver_id == current_driver.id,
            CustomerDriverAssignment.is_active.is_(True),
        )
        .order_by(
            CustomerDriverAssignment.assigned_at.desc(),
            CustomerDriverAssignment.id.desc(),
        )
    ).unique().all()

    return list(assignments)

def get_customer_active_driver_id(
    db: Session,
    customer_id: int,
) -> int | None:
    """
    Return the active driver's user ID for order generation.

    This helper will later be used by the automatic order service.
    """

    driver_id = db.scalar(
        select(CustomerDriverAssignment.driver_id).where(
            CustomerDriverAssignment.customer_id == customer_id,
            CustomerDriverAssignment.is_active.is_(True),
        )
    )

    return driver_id