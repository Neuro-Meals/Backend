from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import require_roles, get_current_user
from app.modules.coupons.models import Coupon, DiscountType
from app.modules.coupons.schemas import (
    CouponCreate,
    CouponResponse,
    CouponUpdate,
    CouponValidateRequest,
)
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/coupons", tags=["Coupons"])


ADMIN_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.FINANCE_MANAGER,
)


def calculate_discount(coupon: Coupon, amount: float) -> float:
    if coupon.discount_type == DiscountType.PERCENTAGE.value:
        return min(amount, amount * (coupon.discount_value / 100))

    return min(amount, coupon.discount_value)


def validate_coupon_rules(coupon: Coupon, amount: float):
    now = datetime.utcnow()

    if not coupon.is_active:
        raise HTTPException(status_code=400, detail="Coupon is inactive")

    if coupon.starts_at and coupon.starts_at > now:
        raise HTTPException(status_code=400, detail="Coupon is not active yet")

    if coupon.expires_at and coupon.expires_at < now:
        raise HTTPException(status_code=400, detail="Coupon has expired")

    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        raise HTTPException(status_code=400, detail="Coupon usage limit reached")

    if coupon.min_order_amount is not None and amount < coupon.min_order_amount:
        raise HTTPException(status_code=400, detail="Amount is below coupon minimum")


@router.post("/", response_model=CouponResponse)
def create_coupon(
    payload: CouponCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    code = payload.code.strip().upper()

    exists = db.query(Coupon).filter(Coupon.code == code).first()
    if exists:
        raise HTTPException(status_code=400, detail="Coupon already exists")

    coupon = Coupon(
        **payload.model_dump(exclude={"code", "discount_type"}),
        code=code,
        discount_type=payload.discount_type.value,
    )

    db.add(coupon)
    db.commit()
    db.refresh(coupon)

    return coupon


@router.get("/")
def list_coupons(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Coupon)

    if search:
        value = f"%{search.upper()}%"
        query = query.filter(Coupon.code.ilike(value))

    if is_active is not None:
        query = query.filter(Coupon.is_active == is_active)

    total = query.count()

    coupons = (
        query.order_by(Coupon.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": coupons,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/{coupon_id}", response_model=CouponResponse)
def get_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    return coupon


@router.put("/{coupon_id}", response_model=CouponResponse)
def update_coupon(
    coupon_id: int,
    payload: CouponUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "discount_type" in update_data and update_data["discount_type"] is not None:
        update_data["discount_type"] = update_data["discount_type"].value

    for field, value in update_data.items():
        setattr(coupon, field, value)

    db.commit()
    db.refresh(coupon)

    return coupon


@router.delete("/{coupon_id}")
def delete_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    db.delete(coupon)
    db.commit()

    return {"message": "Coupon deleted successfully"}


@router.post("/validate")
def validate_coupon(
    payload: CouponValidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    coupon = db.query(Coupon).filter(Coupon.code == payload.code.strip().upper()).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    validate_coupon_rules(coupon, payload.amount)

    discount = calculate_discount(coupon, payload.amount)
    final_amount = max(payload.amount - discount, 0)

    return {
        "valid": True,
        "coupon_id": coupon.id,
        "code": coupon.code,
        "discount": discount,
        "original_amount": payload.amount,
        "final_amount": final_amount,
    }