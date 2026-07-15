from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.chef.admin_schemas import (
    AssignChefRoleRequest,
    ChefCreate,
    ChefResponse,
    ChefUpdate,
)
from app.modules.users.models import User, UserRole
from app.modules.users.service import (
    get_user_by_email,
    get_user_by_phone,
    normalize_phone,
)


router = APIRouter(
    prefix="/admin/chefs",
    tags=["Admin Chef Management"],
)


def chef_payload(user: User) -> dict:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": (
            f"{user.first_name} {user.last_name}"
        ),
        "email": user.email,
        "phone": user.phone,
        "location": getattr(user, "location", None),
        "address": getattr(user, "address", None),
        "role": (
            user.role.value
            if hasattr(user.role, "value")
            else user.role
        ),
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
        "updated_at": getattr(user, "updated_at", None),
    }


def get_chef_or_404(
    db: Session,
    chef_id: int,
) -> User:
    chef = (
        db.query(User)
        .filter(
            User.id == chef_id,
            User.role == UserRole.CHEF,
        )
        .first()
    )

    if chef is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chef not found",
        )

    return chef


@router.post(
    "/",
    response_model=ChefResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_chef(
    payload: ChefCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    normalized_email = payload.email.strip().lower()
    normalized_phone = normalize_phone(payload.phone)

    if get_user_by_email(db, normalized_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    if get_user_by_phone(db, normalized_phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is already registered",
        )

    chef = User(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=normalized_email,
        phone=normalized_phone,
        hashed_password=hash_password(payload.password),

        location=(
            payload.location.strip()
            if payload.location
            else None
        ),
        address=(
            payload.address.strip()
            if payload.address
            else None
        ),

        role=UserRole.CHEF,

        # The admin creates the chef directly.
        is_verified=True,
        is_active=True,

        # Customer nutrition-profile fields are not required for chefs.
        gender=None,
        age=None,
        height_cm=None,
        weight_kg=None,
        fitness_goal=None,
        dietary_preference=None,
        allergies=[],

        email_otp=None,
        email_otp_expires_at=None,
    )

    db.add(chef)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chef could not be created because of duplicate data",
        ) from exc

    db.refresh(chef)

    return chef_payload(chef)


@router.get("/")
def list_chefs(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = (
        db.query(User)
        .filter(User.role == UserRole.CHEF)
    )

    if search:
        value = f"%{search.strip()}%"

        query = query.filter(
            or_(
                User.first_name.ilike(value),
                User.last_name.ilike(value),
                User.email.ilike(value),
                User.phone.ilike(value),
                User.location.ilike(value),
            )
        )

    if is_active is not None:
        query = query.filter(
            User.is_active.is_(is_active)
        )

    total = query.count()

    chefs = (
        query.order_by(User.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": [
            chef_payload(chef)
            for chef in chefs
        ],
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (
                (total + limit - 1) // limit
                if total
                else 0
            ),
        },
    }


@router.get(
    "/{chef_id}",
    response_model=ChefResponse,
)
def get_chef(
    chef_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    chef = get_chef_or_404(
        db=db,
        chef_id=chef_id,
    )

    return chef_payload(chef)


@router.patch(
    "/{chef_id}",
    response_model=ChefResponse,
)
def update_chef(
    chef_id: int,
    payload: ChefUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    chef = get_chef_or_404(
        db=db,
        chef_id=chef_id,
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    if "email" in update_data:
        normalized_email = (
            str(update_data["email"])
            .strip()
            .lower()
        )

        existing_email = (
            db.query(User)
            .filter(
                User.email == normalized_email,
                User.id != chef.id,
            )
            .first()
        )

        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already used by another user",
            )

        chef.email = normalized_email

    if "phone" in update_data:
        normalized_phone = normalize_phone(
            update_data["phone"]
        )

        existing_phone = (
            db.query(User)
            .filter(
                User.phone == normalized_phone,
                User.id != chef.id,
            )
            .first()
        )

        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number is already used by another user",
            )

        chef.phone = normalized_phone

    if "first_name" in update_data:
        chef.first_name = (
            update_data["first_name"].strip()
        )

    if "last_name" in update_data:
        chef.last_name = (
            update_data["last_name"].strip()
        )

    if "location" in update_data:
        chef.location = (
            update_data["location"].strip()
            if update_data["location"]
            else None
        )

    if "address" in update_data:
        chef.address = (
            update_data["address"].strip()
            if update_data["address"]
            else None
        )

    if "is_active" in update_data:
        chef.is_active = update_data["is_active"]

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chef could not be updated",
        ) from exc

    db.refresh(chef)

    return chef_payload(chef)


@router.patch(
    "/{chef_id}/activate",
    response_model=ChefResponse,
)
def activate_chef(
    chef_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    chef = get_chef_or_404(
        db=db,
        chef_id=chef_id,
    )

    if chef.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chef is already active",
        )

    chef.is_active = True

    db.commit()
    db.refresh(chef)

    return chef_payload(chef)


@router.patch(
    "/{chef_id}/deactivate",
    response_model=ChefResponse,
)
def deactivate_chef(
    chef_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    chef = get_chef_or_404(
        db=db,
        chef_id=chef_id,
    )

    if not chef.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chef is already inactive",
        )

    chef.is_active = False

    db.commit()
    db.refresh(chef)

    return chef_payload(chef)


@router.post(
    "/assign-existing-user",
    response_model=ChefResponse,
)
def assign_existing_user_as_chef(
    payload: AssignChefRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    user = (
        db.query(User)
        .filter(User.id == payload.user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.role == UserRole.CHEF:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a chef",
        )

    if user.role in {
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An administrator cannot be converted into a chef",
        )

    user.role = UserRole.CHEF
    user.is_active = True

    db.commit()
    db.refresh(user)

    return chef_payload(user)


@router.patch(
    "/{chef_id}/remove-role",
    response_model=ChefResponse,
)
def remove_chef_role(
    chef_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    chef = get_chef_or_404(
        db=db,
        chef_id=chef_id,
    )

    chef.role = UserRole.CUSTOMER

    db.commit()
    db.refresh(chef)

    response = chef_payload(chef)
    response["role"] = UserRole.CUSTOMER.value

    return response