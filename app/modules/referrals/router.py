from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import (
    get_current_user,
    require_roles,
)
from app.modules.coupons.models import Coupon
from app.modules.referrals.models import (
    Referral,
    ReferralCode,
    ReferralEarning,
    ReferralEarningStatus,
    ReferralProgramSetting,
    ReferralReward,
)
from app.modules.referrals.schemas import (
    ReferralProgramSettingUpdate,
)
from app.modules.referrals.service import (
    ensure_referral_code,
    get_program_setting,
    sync_program_setting_legacy_fields,
)
from app.modules.users.models import (
    User,
    UserRole,
)


router = APIRouter(
    prefix="/referrals",
    tags=["Referrals"],
)

ADMIN_ROLES = (
    UserRole.ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.FINANCE_MANAGER,
)


def _money_float(value) -> float:
    return float(
        Decimal(str(value or 0))
    )


@router.get("/me")
def my_referrals(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    code = ensure_referral_code(
        db,
        current_user,
    )

    referrals = (
        db.query(Referral)
        .filter(
            Referral.referrer_user_id
            == current_user.id
        )
        .order_by(
            Referral.id.desc()
        )
        .all()
    )

    legacy_rewards = (
        db.query(ReferralReward)
        .filter(
            ReferralReward.user_id
            == current_user.id
        )
        .order_by(
            ReferralReward.id.desc()
        )
        .all()
    )

    earnings = (
        db.query(ReferralEarning)
        .filter(
            ReferralEarning.referrer_user_id
            == current_user.id
        )
        .order_by(
            ReferralEarning.id.desc()
        )
        .all()
    )

    reward_rows = []

    # Legacy rewards remain visible.
    for reward in legacy_rewards:
        coupon = None

        if reward.coupon_id:
            coupon = (
                db.query(Coupon)
                .filter(
                    Coupon.id == reward.coupon_id
                )
                .first()
            )

        reward_rows.append(
            {
                "id": f"legacy-{reward.id}",
                "earning_id": None,
                "coupon_id": reward.coupon_id,
                "coupon_code": (
                    coupon.code
                    if coupon
                    else None
                ),
                "reward_type": (
                    reward.reward_type
                ),
                "reward_value": (
                    reward.reward_value
                ),
                "status": reward.status,
                "expires_at": reward.expires_at,
                "used_at": reward.used_at,
                "created_at": reward.created_at,
            }
        )

    for earning in earnings:
        coupon = None

        if earning.coupon_id:
            coupon = (
                db.query(Coupon)
                .filter(
                    Coupon.id == earning.coupon_id
                )
                .first()
            )

        reward_rows.append(
            {
                "id": f"earning-{earning.id}",
                "earning_id": earning.id,
                "coupon_id": earning.coupon_id,
                "coupon_code": (
                    coupon.code
                    if coupon
                    else None
                ),
                "reward_type": (
                    earning.reward_mode
                ),
                "reward_value": _money_float(
                    earning.reward_amount
                ),
                "payment_amount": _money_float(
                    earning.payment_amount
                ),
                "reward_rate": _money_float(
                    earning.reward_rate
                ),
                "payment_id": earning.payment_id,
                "subscription_id": (
                    earning.subscription_id
                ),
                "referred_user_id": (
                    earning.referred_user_id
                ),
                "status": earning.status,
                "expires_at": earning.expires_at,
                "used_at": earning.used_at,
                "created_at": earning.created_at,
            }
        )

    available_total = sum(
        _money_float(e.reward_amount)
        for e in earnings
        if e.status
        == ReferralEarningStatus.AVAILABLE.value
    )

    used_total = sum(
        _money_float(e.reward_amount)
        for e in earnings
        if e.status
        == ReferralEarningStatus.USED.value
    )

    total_earned = sum(
        _money_float(e.reward_amount)
        for e in earnings
        if e.status
        not in {
            ReferralEarningStatus.CANCELLED.value,
        }
    )

    db.commit()

    return {
        "referral_code": code.code,
        "total_referrals": len(
            referrals
        ),
        "pending_referrals": sum(
            1
            for referral in referrals
            if referral.status == "pending"
        ),
        "rewarded_referrals": sum(
            1
            for referral in referrals
            if referral.status == "rewarded"
        ),
        "successful_transactions": len(
            earnings
        ),
        "total_earned": round(
            total_earned,
            2,
        ),
        "available_credit": round(
            available_total,
            2,
        ),
        "used_credit": round(
            used_total,
            2,
        ),
        "rewards": reward_rows,
        "earnings": reward_rows,
        "referrals": [
            {
                "id": referral.id,
                "referred_user_id": (
                    referral.referred_user_id
                ),
                "status": referral.status,
                "created_at": (
                    referral.created_at
                ),
                "qualified_at": (
                    referral.qualified_at
                ),
                "rewarded_at": (
                    referral.rewarded_at
                ),
            }
            for referral in referrals
        ],
    }


@router.get("/me/earnings")
def my_referral_earnings(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
    status: str | None = Query(None),
    page: int = Query(
        1,
        ge=1,
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),
):
    query = db.query(
        ReferralEarning
    ).filter(
        ReferralEarning.referrer_user_id
        == current_user.id
    )

    if status:
        query = query.filter(
            ReferralEarning.status == status
        )

    total = query.count()

    rows = (
        query.order_by(
            ReferralEarning.id.desc()
        )
        .offset(
            (page - 1) * limit
        )
        .limit(limit)
        .all()
    )

    return {
        "data": rows,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (
                total + limit - 1
            ) // limit,
        },
    }


@router.get("/admin")
def admin_referrals(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *ADMIN_ROLES
        )
    ),
    status: str | None = Query(None),
    page: int = Query(
        1,
        ge=1,
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),
):
    query = db.query(
        Referral
    )

    if status:
        query = query.filter(
            Referral.status == status
        )

    total = query.count()

    rows = (
        query.order_by(
            Referral.id.desc()
        )
        .offset(
            (page - 1) * limit
        )
        .limit(limit)
        .all()
    )

    earnings_total = (
        db.query(
            func.coalesce(
                func.sum(
                    ReferralEarning.reward_amount
                ),
                0,
            )
        )
        .scalar()
    )

    available_total = (
        db.query(
            func.coalesce(
                func.sum(
                    ReferralEarning.reward_amount
                ),
                0,
            )
        )
        .filter(
            ReferralEarning.status
            == ReferralEarningStatus.AVAILABLE.value
        )
        .scalar()
    )

    return {
        "data": [
            {
                "id": row.id,
                "referrer_user_id": (
                    row.referrer_user_id
                ),
                "referred_user_id": (
                    row.referred_user_id
                ),
                "referral_code_id": (
                    row.referral_code_id
                ),
                "status": row.status,
                "qualified_subscription_id": (
                    row.qualified_subscription_id
                ),
                "qualified_payment_id": (
                    row.qualified_payment_id
                ),
                "created_at": row.created_at,
                "qualified_at": (
                    row.qualified_at
                ),
                "rewarded_at": (
                    row.rewarded_at
                ),
            }
            for row in rows
        ],
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (
                total + limit - 1
            ) // limit,
            "earnings_total": _money_float(
                earnings_total
            ),
            "available_credit_total": (
                _money_float(
                    available_total
                )
            ),
        },
    }


@router.get("/admin/earnings")
def admin_referral_earnings(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *ADMIN_ROLES
        )
    ),
    referrer_user_id: int | None = Query(
        None
    ),
    referred_user_id: int | None = Query(
        None
    ),
    status: str | None = Query(None),
    page: int = Query(
        1,
        ge=1,
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
    ),
):
    query = db.query(
        ReferralEarning
    )

    if referrer_user_id is not None:
        query = query.filter(
            ReferralEarning.referrer_user_id
            == referrer_user_id
        )

    if referred_user_id is not None:
        query = query.filter(
            ReferralEarning.referred_user_id
            == referred_user_id
        )

    if status:
        query = query.filter(
            ReferralEarning.status == status
        )

    total = query.count()

    rows = (
        query.order_by(
            ReferralEarning.id.desc()
        )
        .offset(
            (page - 1) * limit
        )
        .limit(limit)
        .all()
    )

    return {
        "data": rows,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (
                total + limit - 1
            ) // limit,
        },
    }


@router.get("/admin/settings")
def referral_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *ADMIN_ROLES
        )
    ),
):
    setting = get_program_setting(db)
    sync_program_setting_legacy_fields(
        setting
    )

    db.commit()
    db.refresh(setting)

    return setting


@router.patch("/admin/settings")
def update_referral_settings(
    payload: ReferralProgramSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            *ADMIN_ROLES
        )
    ),
):
    setting = get_program_setting(db)

    data = payload.model_dump(
        exclude_unset=True,
    )

    # Pydantic enum members serialize to enum instances here.
    for key in (
        "reward_mode",
        "commission_scope",
    ):
        value = data.get(key)

        if hasattr(
            value,
            "value",
        ):
            data[key] = value.value

    # Legacy UI sends reward_amount. Treat it as reward_value.
    if (
        "reward_amount" in data
        and "reward_value" not in data
    ):
        data["reward_value"] = (
            data["reward_amount"]
        )

    for field, value in data.items():
        setattr(
            setting,
            field,
            value,
        )

    # Fixed-first-payment always has first-payment scope.
    if (
        setting.reward_mode
        == "fixed_first_payment"
    ):
        setting.commission_scope = (
            "first_payment_only"
        )

    sync_program_setting_legacy_fields(
        setting
    )

    db.commit()
    db.refresh(setting)

    return setting
