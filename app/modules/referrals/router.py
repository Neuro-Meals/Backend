from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.coupons.models import Coupon
from app.modules.referrals.models import Referral, ReferralCode, ReferralReward
from app.modules.referrals.schemas import ReferralProgramSettingUpdate
from app.modules.referrals.service import ensure_referral_code, get_program_setting
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/referrals", tags=["Referrals"])
ADMIN_ROLES = (UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.FINANCE_MANAGER)


@router.get("/me")
def my_referrals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code = ensure_referral_code(db, current_user)
    db.commit()

    referrals = db.query(Referral).filter(Referral.referrer_user_id == current_user.id).order_by(Referral.id.desc()).all()
    rewards = db.query(ReferralReward).filter(ReferralReward.user_id == current_user.id).order_by(ReferralReward.id.desc()).all()

    reward_rows = []
    for reward in rewards:
        coupon = db.query(Coupon).filter(Coupon.id == reward.coupon_id).first() if reward.coupon_id else None
        reward_rows.append({
            "id": reward.id,
            "coupon_id": reward.coupon_id,
            "coupon_code": coupon.code if coupon else None,
            "reward_type": reward.reward_type,
            "reward_value": reward.reward_value,
            "status": reward.status,
            "expires_at": reward.expires_at,
            "used_at": reward.used_at,
            "created_at": reward.created_at,
        })

    return {
        "referral_code": code.code,
        "total_referrals": len(referrals),
        "pending_referrals": sum(1 for r in referrals if r.status == "pending"),
        "rewarded_referrals": sum(1 for r in referrals if r.status == "rewarded"),
        "rewards": reward_rows,
        "referrals": [
            {
                "id": r.id,
                "referred_user_id": r.referred_user_id,
                "status": r.status,
                "created_at": r.created_at,
                "qualified_at": r.qualified_at,
                "rewarded_at": r.rewarded_at,
            }
            for r in referrals
        ],
    }


@router.get("/admin")
def admin_referrals(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    query = db.query(Referral)
    if status:
        query = query.filter(Referral.status == status)
    total = query.count()
    rows = query.order_by(Referral.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "data": rows,
        "meta": {"total": total, "page": page, "limit": limit, "pages": (total + limit - 1) // limit},
    }


@router.get("/admin/settings")
def referral_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    setting = get_program_setting(db)
    db.commit()
    db.refresh(setting)
    return setting


@router.patch("/admin/settings")
def update_referral_settings(
    payload: ReferralProgramSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    setting = get_program_setting(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(setting, field, value)
    db.commit()
    db.refresh(setting)
    return setting
