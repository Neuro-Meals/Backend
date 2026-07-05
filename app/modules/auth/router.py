from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.email import send_email_otp
from app.core.security import create_access_token, verify_password
from app.db.database import get_db
from app.modules.auth.schemas import LoginRequest, TokenResponse
from app.modules.users.schemas import UserCreate, UserResponse, VerifyEmailOTP
from app.modules.users.service import create_user, get_user_by_email


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing_user = get_user_by_email(db, payload.email)

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = create_user(db, payload)

    send_email_otp(user.email, user.email_otp)

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


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, payload.email)

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")

    token = create_access_token(subject=str(user.id))

    return TokenResponse(access_token=token)