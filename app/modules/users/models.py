from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.email import send_email_otp
from app.core.security import (
    create_access_token,
    verify_password,
    hash_password,
    generate_otp,
)
from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    LoginRequest,
    TokenResponse,
    ResendVerificationOTP,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
)
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserResponse, VerifyEmailOTP
from app.modules.users.service import create_user, get_user_by_email


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing_user = get_user_by_email(db, payload.email)

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = create_user(db, payload)

    send_email_otp(user.email, user.email_otp, purpose="verification")

    return user


@router.post("/verify-email")
def verify_email(payload: VerifyEmailOTP, db: Session = Depends(get_db)):
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

    return {"message": "Email verified successfully"}


@router.post("/resend-verification-otp")
def resend_verification_otp(
    payload: ResendVerificationOTP,
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, payload.email)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email is already verified"}

    otp = generate_otp()

    user.email_otp = otp
    user.email_otp_expires_at = datetime.utcnow() + timedelta(minutes=10)

    db.commit()

    send_email_otp(user.email, otp, purpose="verification")

    return {"message": "Verification OTP sent successfully"}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
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

    return TokenResponse(access_token=token)


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, payload.email)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp = generate_otp()

    user.password_reset_otp = otp
    user.password_reset_otp_expires_at = datetime.utcnow() + timedelta(minutes=10)

    db.commit()

    send_email_otp(user.email, otp, purpose="password_reset")

    return {"message": "Password reset OTP sent successfully"}


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, payload.email)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.password_reset_otp != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if (
        not user.password_reset_otp_expires_at
        or user.password_reset_otp_expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="OTP has expired")

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_otp = None
    user.password_reset_otp_expires_at = None

    db.commit()

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

    return {"message": "Password changed successfully"}