from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import generate_otp, hash_password
from app.modules.users.models import User, UserRole
from app.modules.users.schemas import UserCreate


def normalize_phone(phone: str) -> str:
    return (
        phone.strip()
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )


def get_user_by_id(
    db: Session,
    user_id: int,
) -> User | None:
    return (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )


def get_user_by_email(
    db: Session,
    email: str,
) -> User | None:
    normalized_email = email.strip().lower()

    return (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )


def get_user_by_phone(
    db: Session,
    phone: str,
) -> User | None:
    normalized_phone = normalize_phone(phone)

    return (
        db.query(User)
        .filter(User.phone == normalized_phone)
        .first()
    )


def create_user(
    db: Session,
    payload: UserCreate,
) -> User:
    otp = generate_otp()

    user = User(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=payload.email.strip().lower(),
        phone=normalize_phone(payload.phone),
        hashed_password=hash_password(payload.password),

        location=payload.location.strip(),
        address=payload.address.strip(),

        role=UserRole.CUSTOMER,
        is_verified=False,
        is_active=True,

        email_otp=otp,
        email_otp_expires_at=(
            datetime.utcnow() + timedelta(minutes=10)
        ),

        # These values will be completed later from the profile page.
        gender=None,
        age=None,
        height_cm=None,
        weight_kg=None,
        fitness_goal=None,
        dietary_preference=None,
        allergies=[],
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user