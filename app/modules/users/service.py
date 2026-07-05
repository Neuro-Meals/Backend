from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.security import hash_password, generate_otp
from app.modules.users.models import User, UserRole
from app.modules.users.schemas import UserCreate


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, payload: UserCreate, role: UserRole = UserRole.CUSTOMER) -> User:
    otp = generate_otp()

    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        location=payload.location,
        address=payload.address,
        gender=payload.gender,
        age=payload.age,
        height_cm=payload.height_cm,
        weight_kg=payload.weight_kg,
        fitness_goal=payload.fitness_goal,
        dietary_preference=payload.dietary_preference,
        allergies=payload.allergies,
        hashed_password=hash_password(payload.password),
        role=role,
        email_otp=otp,
        email_otp_expires_at=datetime.utcnow() + timedelta(minutes=10),
        is_verified=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user