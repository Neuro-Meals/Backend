from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.users.models import User, UserRole
from app.modules.users.schemas import UserResponse, UserUpdateRole
from app.modules.users.service import get_user_by_id


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def my_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),

    search: str | None = Query(None, description="Search by name, email, phone, or location"),
    role: UserRole | None = Query(None, description="Filter by role"),
    is_verified: bool | None = Query(None, description="Filter verified/unverified users"),

    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(User)

    if search:
        search_value = f"%{search}%"
        query = query.filter(
            or_(
                User.first_name.ilike(search_value),
                User.last_name.ilike(search_value),
                User.email.ilike(search_value),
                User.phone.ilike(search_value),
                User.location.ilike(search_value),
            )
        )

    if role:
        query = query.filter(User.role == role)

    if is_verified is not None:
        query = query.filter(User.is_verified == is_verified)

    total = query.count()

    users = (
        query.order_by(User.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": users,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.patch("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: UserUpdateRole,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    user = get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = payload.role
    db.commit()
    db.refresh(user)

    return user