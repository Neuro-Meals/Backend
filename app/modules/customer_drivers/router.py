from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import (
    get_current_user,
    require_roles,
)
from app.modules.customer_drivers.schemas import (
    CustomerDriverAssignRequest,
    CustomerDriverAssignmentListResponse,
    CustomerDriverAssignmentResponse,
    CustomerDriverDeleteResponse,
    CustomerDriverUpdateRequest,
)
from app.modules.customer_drivers.service import (
    assign_driver_to_customer,
    change_customer_driver,
    deactivate_customer_driver,
    get_active_assignment_for_customer,
    get_customer_assignment_history,
    list_current_driver_customers,
    list_customer_driver_assignments,
    list_driver_customers,
)
from app.modules.users.models import User, UserRole

router = APIRouter(
    prefix="/customer-drivers",
    tags=["Customer Drivers"],
)

@router.post(
    "/assign",
    response_model=CustomerDriverAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_driver(
    payload: CustomerDriverAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    return assign_driver_to_customer(
        db=db,
        payload=payload,
        assigned_by_user=current_user,
    )

@router.patch(
    "/customer/{customer_id}",
    response_model=CustomerDriverAssignmentResponse,
)
def change_driver(
    customer_id: int,
    payload: CustomerDriverUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    return change_customer_driver(
        db=db,
        customer_id=customer_id,
        payload=payload,
        assigned_by_user=current_user,
    )

@router.delete(
    "/customer/{customer_id}",
    response_model=CustomerDriverDeleteResponse,
)
def remove_driver(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    deactivate_customer_driver(
        db=db,
        customer_id=customer_id,
    )

    return CustomerDriverDeleteResponse(
        success=True,
        message="Driver assignment removed successfully.",
    )

@router.get(
    "/customer/{customer_id}",
    response_model=CustomerDriverAssignmentResponse,
)
def get_customer_driver(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    return get_active_assignment_for_customer(
        db=db,
        customer_id=customer_id,
    )

@router.get(
    "/customer/{customer_id}/history",
    response_model=list[CustomerDriverAssignmentResponse],
)
def customer_history(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    return get_customer_assignment_history(
        db=db,
        customer_id=customer_id,
    )

@router.get(
    "/driver/{driver_id}",
    response_model=list[CustomerDriverAssignmentResponse],
)
def driver_customers(
    driver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    return list_driver_customers(
        db=db,
        driver_id=driver_id,
    )

@router.get(
    "/me/customers",
    response_model=list[CustomerDriverAssignmentResponse],
)
def my_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_current_driver_customers(
        db=db,
        current_driver=current_user,
    )
    
@router.get(
    "",
    response_model=CustomerDriverAssignmentListResponse,
)
def get_assignments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    active_only: bool = True,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    total, items = list_customer_driver_assignments(
        db=db,
        page=page,
        page_size=page_size,
        active_only=active_only,
        search=search,
    )

    return CustomerDriverAssignmentListResponse(
        total=total,
        items=items,
    )