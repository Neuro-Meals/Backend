from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.email import send_email_otp
from app.core.security import create_access_token, generate_otp, hash_password, verify_password
from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    CurrentSubscriptionResponse,
    ForgotPasswordRequest,
    LoggedInUser,
    LoginRequest,
    ResendVerificationOTP,
    ResetPasswordRequest,
    TokenResponse,
)
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import Subscription, SubscriptionStatus
from app.modules.users.models import User
from app.modules.users.rbac_service import get_user_permissions
from app.modules.users.schemas import UserCreate, UserResponse, VerifyEmailOTP
from app.modules.users.service import create_user, get_user_by_email, get_user_by_phone
from fastapi import Request
from app.core.rate_limiter import get_client_ip, hash_key, normalize_identifier, rate_limit


router = APIRouter(prefix="/auth", tags=["Auth"])


def get_current_subscription_payload(db: Session, user_id: int):
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(
                [
                    SubscriptionStatus.PENDING_PAYMENT,
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.PAUSED,
                ]
            ),
        )
        .order_by(Subscription.id.desc())
        .first()
    )

    if not subscription:
        return None

    plan = db.query(MealPlan).filter(MealPlan.id == subscription.plan_id).first()

    return CurrentSubscriptionResponse(
        id=subscription.id,
        plan_id=subscription.plan_id,
        plan_name=plan.name_en if plan else None,
        status=subscription.status.value,
        payment_status=subscription.payment_status.value,
        amount=subscription.amount,
        start_date=subscription.start_date,
        end_date=subscription.end_date,
    )


def build_logged_in_user(
    db: Session,
    user: User,
) -> LoggedInUser:
    return LoggedInUser(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone=user.phone,
        role=user.role.value,
        permissions=get_user_permissions(db, user),

        location=user.location,
        address=user.address,

        gender=user.gender.value if user.gender else None,
        age=user.age,
        height_cm=user.height_cm,
        weight_kg=user.weight_kg,
        fitness_goal=(
            user.fitness_goal.value
            if user.fitness_goal
            else None
        ),
        dietary_preference=user.dietary_preference,
        allergies=user.allergies or [],

        subscription=get_current_subscription_payload(
            db,
            user.id,
        ),
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    try:
        existing_user = get_user_by_email(db, payload.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        existing_user = get_user_by_phone(db, payload.phone)
        if existing_user:
            raise HTTPException(status_code=400, detail="Phone number already registered")

        user = create_user(db, payload)
        send_email_otp(user.email, user.email_otp, purpose="verification")
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-email")
def verify_email(
    payload: VerifyEmailOTP,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = get_client_ip(request)
    email_key = hash_key(normalize_identifier(payload.email))

    rate_limit(f"rate:verify-email:ip:{ip}", limit=5, window_seconds=600)
    rate_limit(f"rate:verify-email:email:{email_key}", limit=5, window_seconds=600)

    user = get_user_by_email(db, payload.email)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email already verified"}

    if user.email_otp != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if not user.email_otp_expires_at or user.email_otp_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP has expired")

    user.is_verified = True
    user.email_otp = None
    user.email_otp_expires_at = None

    db.commit()
    db.refresh(user)

    return {"message": "Email verified successfully"}


@router.post("/resend-verification-otp")
def resend_verification_otp(
    payload: ResendVerificationOTP,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = get_client_ip(request)
    email_key = hash_key(normalize_identifier(payload.email))

    rate_limit(f"rate:resend-otp:ip:{ip}", limit=3, window_seconds=60)
    rate_limit(f"rate:resend-otp:email:{email_key}", limit=1, window_seconds=60)

    user = get_user_by_email(db, payload.email)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email is already verified"}

    otp = generate_otp()
    user.email_otp = otp
    user.email_otp_expires_at = datetime.utcnow() + timedelta(minutes=10)

    db.commit()
    db.refresh(user)

    send_email_otp(user.email, otp, purpose="verification")

    return {"message": "Verification OTP sent successfully"}


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = get_client_ip(request)
    email_key = hash_key(normalize_identifier(payload.email))

    rate_limit(f"rate:login:ip:{ip}", limit=5, window_seconds=60)
    rate_limit(f"rate:login:email:{email_key}", limit=5, window_seconds=60)

    user = get_user_by_email(db, payload.email)

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Please verify your email first",
                "email": user.email,
                "requires_verification": True,
            },
        )

    token = create_access_token(subject=str(user.id))

    return TokenResponse(
        access_token=token,
        user=build_logged_in_user(db, user),
    )

@router.get("/me", response_model=LoggedInUser)
def me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return build_logged_in_user(db, current_user)


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = get_client_ip(request)
    email_key = hash_key(normalize_identifier(payload.email))

    rate_limit(f"rate:forgot-password:ip:{ip}", limit=10, window_seconds=3600)
    rate_limit(f"rate:forgot-password:email:{email_key}", limit=3, window_seconds=3600)

    user = get_user_by_email(db, payload.email)

    if user:
        otp = generate_otp()
        user.password_reset_otp = otp
        user.password_reset_otp_expires_at = datetime.utcnow() + timedelta(minutes=10)

        db.commit()
        db.refresh(user)

        send_email_otp(user.email, otp, purpose="password_reset")

    return {
        "message": "If the account exists, a password reset email has been sent."
    }


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = get_client_ip(request)
    email_key = hash_key(normalize_identifier(payload.email))

    rate_limit(f"rate:reset-password:ip:{ip}", limit=5, window_seconds=600)
    rate_limit(f"rate:reset-password:email:{email_key}", limit=5, window_seconds=600)

    user = get_user_by_email(db, payload.email)

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    if user.password_reset_otp != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    if not user.password_reset_otp_expires_at or user.password_reset_otp_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_otp = None
    user.password_reset_otp_expires_at = None

    db.commit()
    db.refresh(user)

    return {"message": "Password reset successfully"}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    current_user.hashed_password = hash_password(payload.new_password)

    db.commit()
    db.refresh(current_user)

    return {"message": "Password changed successfully"}

