from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.coupons.models import Coupon, CouponRedemption, CouponRule
from app.modules.coupons.schemas import (
    CouponCreate,
    CouponRedemptionResponse,
    CouponResponse,
    CouponUpdate,
    CouponValidateRequest,
)
from app.modules.coupons.service import (
    calculate_discount,
    coupon_to_dict,
    get_valid_coupon,
)
from app.modules.plans.models import MealPlan
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/coupons", tags=["Coupons"])

ADMIN_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.FINANCE_MANAGER,
)


def validate_rule_references(db: Session, plan_id: int | None, user_id: int | None):
    if plan_id is not None and not db.query(MealPlan.id).filter(MealPlan.id == plan_id).first():
        raise HTTPException(status_code=404, detail="Applicable meal plan not found")
    if user_id is not None and not db.query(User.id).filter(User.id == user_id).first():
        raise HTTPException(status_code=404, detail="Allowed customer not found")


@router.post("/", response_model=CouponResponse)
def create_coupon(
    payload: CouponCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    code = payload.code.strip().upper()
    if db.query(Coupon.id).filter(Coupon.code == code).first():
        raise HTTPException(status_code=400, detail="Coupon already exists")

    validate_rule_references(db, payload.applicable_plan_id, payload.allowed_user_id)

    coupon = Coupon(
        code=code,
        description=payload.description,
        discount_type=payload.discount_type.value,
        discount_value=payload.discount_value,
        max_uses=payload.max_uses,
        min_order_amount=payload.min_order_amount,
        starts_at=payload.starts_at,
        expires_at=payload.expires_at,
        is_active=payload.is_active,
    )
    db.add(coupon)
    db.flush()
    db.add(CouponRule(
        coupon_id=coupon.id,
        max_uses_per_user=payload.max_uses_per_user,
        applicable_plan_id=payload.applicable_plan_id,
        allowed_user_id=payload.allowed_user_id,
        new_customers_only=payload.new_customers_only,
        source="admin",
    ))
    db.commit()
    db.refresh(coupon)
    return coupon_to_dict(coupon)


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
        query = query.filter(Coupon.code.ilike(f"%{search.upper()}%"))
    if is_active is not None:
        query = query.filter(Coupon.is_active == is_active)

    total = query.count()
    rows = query.order_by(Coupon.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "data": [coupon_to_dict(row) for row in rows],
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/redemptions", response_model=list[CouponRedemptionResponse])
def list_redemptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    coupon_id: int | None = Query(None),
    user_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    query = db.query(CouponRedemption)
    if coupon_id is not None:
        query = query.filter(CouponRedemption.coupon_id == coupon_id)
    if user_id is not None:
        query = query.filter(CouponRedemption.user_id == user_id)
    return query.order_by(CouponRedemption.id.desc()).limit(limit).all()


@router.post("/validate")
def validate_coupon(
    payload: CouponValidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    coupon = get_valid_coupon(
        db,
        payload.code,
        payload.amount,
        user_id=current_user.id,
        plan_id=payload.plan_id,
    )
    discount = calculate_discount(coupon, payload.amount)
    final_amount = max(float(payload.amount) - float(discount), 0)
    return {
        "valid": True,
        "coupon_id": coupon.id,
        "code": coupon.code,
        "discount": float(discount),
        "original_amount": float(payload.amount),
        "final_amount": round(final_amount, 2),
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
    return coupon_to_dict(coupon)


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

    data = payload.model_dump(exclude_unset=True)
    validate_rule_references(db, data.get("applicable_plan_id"), data.get("allowed_user_id"))

    core_fields = {
        "description", "discount_value", "max_uses", "min_order_amount",
        "starts_at", "expires_at", "is_active",
    }
    for field in core_fields:
        if field in data:
            setattr(coupon, field, data[field])
    if "discount_type" in data and data["discount_type"] is not None:
        coupon.discount_type = data["discount_type"].value

    rule = coupon.rule or CouponRule(coupon_id=coupon.id, source="admin")
    if coupon.rule is None:
        db.add(rule)
    for field in ("max_uses_per_user", "applicable_plan_id", "allowed_user_id", "new_customers_only"):
        if field in data:
            setattr(rule, field, data[field])

    db.commit()
    db.refresh(coupon)
    return coupon_to_dict(coupon)


@router.delete("/{coupon_id}")
def delete_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    # Preserve finance history once a coupon has been redeemed.
    if db.query(CouponRedemption.id).filter(CouponRedemption.coupon_id == coupon.id).first():
        coupon.is_active = False
        db.commit()
        return {"message": "Coupon has redemption history and was deactivated instead of deleted"}

    db.delete(coupon)
    db.commit()
    return {"message": "Coupon deleted successfully"}
