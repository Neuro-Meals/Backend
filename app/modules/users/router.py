from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.users.models import User, UserRole
from app.modules.users.schemas import UserResponse, UserUpdateRole, UserUpdate
from app.modules.users.service import get_user_by_id
from app.modules.orders.models import Order
from app.modules.subscriptions.models import Subscription, SubscriptionStatus
from app.modules.payments.models import Payment, PaymentRecordStatus
from app.modules.plans.models import MealPlan


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

    # Build enriched user data with orders_count, total_spent, and subscription info
    user_ids = [u.id for u in users]

    # Orders count per user
    orders_counts = {}
    total_spents = {}
    if user_ids:
        order_stats = (
            db.query(
                Order.user_id,
                func.count(Order.id).label("cnt"),
                func.coalesce(func.sum(Order.total_amount), 0).label("spent"),
            )
            .filter(Order.user_id.in_(user_ids))
            .group_by(Order.user_id)
            .all()
        )
        for row in order_stats:
            orders_counts[row.user_id] = row.cnt
            total_spents[row.user_id] = float(row.spent)

    # Active subscription + plan name per user
    subs_info = {}
    if user_ids:
        sub_rows = (
            db.query(
                Subscription.user_id.label("sub_user_id"),
                Subscription.id.label("sub_id"),
                Subscription.status.label("sub_status"),
                Subscription.amount.label("sub_amount"),
                Subscription.start_date.label("sub_start"),
                Subscription.end_date.label("sub_end"),
                Subscription.payment_status.label("sub_payment_status"),
                MealPlan.name_en.label("plan_name"),
                MealPlan.id.label("plan_id"),
            )
            .join(MealPlan, Subscription.plan_id == MealPlan.id)
            .filter(Subscription.user_id.in_(user_ids))
            .order_by(Subscription.id.desc())
            .all()
        )
        for row in sub_rows:
            uid = row.sub_user_id
            # Prefer active subscription; fallback to most recent
            if uid not in subs_info or row.sub_status == SubscriptionStatus.ACTIVE:
                subs_info[uid] = {
                    "id": row.sub_id,
                    "status": row.sub_status.value if hasattr(row.sub_status, 'value') else str(row.sub_status),
                    "amount": float(row.sub_amount),
                    "start_date": row.sub_start.isoformat() if row.sub_start else None,
                    "end_date": row.sub_end.isoformat() if row.sub_end else None,
                    "payment_status": row.sub_payment_status.value if hasattr(row.sub_payment_status, 'value') else str(row.sub_payment_status),
                    "plan_name": row.plan_name,
                    "plan_id": row.plan_id,
                }

    # Build response data
    data = []
    for u in users:
        item = {
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "phone": u.phone,
            "location": u.location,
            "address": u.address,
            "gender": u.gender.value if u.gender else None,
            "age": u.age,
            "height_cm": u.height_cm,
            "weight_kg": u.weight_kg,
            "fitness_goal": u.fitness_goal.value if u.fitness_goal else None,
            "dietary_preference": u.dietary_preference,
            "allergies": u.allergies,
            "role": u.role.value if hasattr(u.role, 'value') else str(u.role),
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "orders_count": orders_counts.get(u.id, 0),
            "total_spent": total_spents.get(u.id, 0.0),
            "subscription": subs_info.get(u.id),
        }
        data.append(item)

    return {
        "data": data,
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


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Soft delete: deactivate instead of hard delete
    user.is_active = False
    db.commit()
    return {"success": True, "message": "User deactivated successfully"}