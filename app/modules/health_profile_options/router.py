from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.health_profile_options.schemas import (
    HealthProfileOptionCreate,
    HealthProfileOptionResponse,
    HealthProfileOptionStatusUpdate,
    HealthProfileOptionType,
    HealthProfileOptionUpdate,
    PublicHealthProfileOptionsResponse,
)
from app.modules.health_profile_options.service import (
    create_option,
    get_option_or_404,
    list_options,
    public_grouped_options,
    update_option,
)
from app.modules.users.models import User, UserRole
from app.modules.users.rbac_service import get_user_permissions


router = APIRouter(prefix="/health-profile-options", tags=["Health Profile Options"])


def require_permission(permission: str):
    def checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if current_user.role == UserRole.SUPER_ADMIN:
            return current_user
        permissions = set(get_user_permissions(db, current_user))
        if permission not in permissions:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: {permission}",
            )
        return current_user

    return checker


@router.get("/public", response_model=PublicHealthProfileOptionsResponse)
def get_public_options(db: Session = Depends(get_db)):
    """Return active options for customer onboarding; authentication is not required."""
    return public_grouped_options(db)


@router.get("/admin")
def get_admin_options(
    option_type: HealthProfileOptionType | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, max_length=150),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings.view")),
):
    rows, total = list_options(
        db,
        option_type=option_type,
        is_active=is_active,
        search=search,
        page=page,
        limit=limit,
    )
    return {
        "data": [HealthProfileOptionResponse.model_validate(row) for row in rows],
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.post(
    "/admin",
    response_model=HealthProfileOptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_option(
    payload: HealthProfileOptionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings.update")),
):
    return create_option(db, payload)


@router.put("/admin/{option_id}", response_model=HealthProfileOptionResponse)
def update_admin_option(
    option_id: int,
    payload: HealthProfileOptionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings.update")),
):
    return update_option(db, get_option_or_404(db, option_id), payload)


@router.patch("/admin/{option_id}/status", response_model=HealthProfileOptionResponse)
def update_admin_option_status(
    option_id: int,
    payload: HealthProfileOptionStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings.update")),
):
    option = get_option_or_404(db, option_id)
    option.is_active = payload.is_active
    db.commit()
    db.refresh(option)
    return option


@router.delete("/admin/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_option(
    option_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings.update")),
):
    option = get_option_or_404(db, option_id)
    db.delete(option)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
