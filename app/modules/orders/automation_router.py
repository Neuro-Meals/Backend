from datetime import date, timedelta

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import (
    require_roles,
)
from app.modules.orders.automation_schemas import (
    AutomaticOrderGenerationResponse,
)
from app.modules.orders.automation_service import (
    confirm_scheduled_orders_for_date,
    generate_orders_for_date,
    preview_orders_for_date,
)
from app.modules.users.models import (
    User,
    UserRole,
)


router = APIRouter(
    prefix="/orders/automation",
    tags=["Automatic Orders"],
)


AUTOMATION_ADMIN_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
)


AUTOMATION_PREVIEW_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.NUTRITION_MANAGER,
    UserRole.CHEF,
    UserRole.DELIVERY_MANAGER,
)


@router.post(
    "/generate",
    response_model=AutomaticOrderGenerationResponse,
)
def generate_automatic_orders(
    target_date: date = Query(
        default_factory=date.today,
        alias="date",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *AUTOMATION_ADMIN_ROLES
        )
    ),
):
    """
    Generate orders for a selected date.

    Orders are generated from active MealAssignment rows,
    not from plan menus.
    """

    return generate_orders_for_date(
        db=db,
        target_date=target_date,
    )


@router.post(
    "/generate-tomorrow",
    response_model=AutomaticOrderGenerationResponse,
)
def generate_tomorrow_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *AUTOMATION_ADMIN_ROLES
        )
    ),
):
    """
    Generate tomorrow's scheduled orders.
    """

    tomorrow = date.today() + timedelta(
        days=1
    )

    return generate_orders_for_date(
        db=db,
        target_date=tomorrow,
    )


@router.post("/confirm-today")
def confirm_today_scheduled_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *AUTOMATION_ADMIN_ROLES
        )
    ),
):
    """
    Change today's scheduled orders to confirmed.
    """

    return confirm_scheduled_orders_for_date(
        db=db,
        target_date=date.today(),
    )


@router.post(
    "/confirm",
)
def confirm_scheduled_orders(
    target_date: date = Query(
        default_factory=date.today,
        alias="date",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *AUTOMATION_ADMIN_ROLES
        )
    ),
):
    """
    Confirm scheduled orders for a selected date.
    """

    return confirm_scheduled_orders_for_date(
        db=db,
        target_date=target_date,
    )


@router.get("/preview")
def preview_automatic_orders(
    target_date: date = Query(
        default_factory=date.today,
        alias="date",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *AUTOMATION_PREVIEW_ROLES
        )
    ),
):
    """
    Preview automatic orders without creating records.
    """

    return preview_orders_for_date(
        db=db,
        target_date=target_date,
    )


@router.get("/preview-tomorrow")
def preview_tomorrow_automatic_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *AUTOMATION_PREVIEW_ROLES
        )
    ),
):
    """
    Preview tomorrow's automatic orders without creating
    records.
    """

    tomorrow = date.today() + timedelta(
        days=1
    )

    return preview_orders_for_date(
        db=db,
        target_date=tomorrow,
    )