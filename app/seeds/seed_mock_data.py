import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.db.database import Base, SessionLocal, engine
from app.modules.users.models import User, UserRole

load_dotenv()

SUPER_ADMIN_FIRST_NAME = os.getenv(
    "SEED_SUPER_ADMIN_FIRST_NAME",
    "Super",
)

SUPER_ADMIN_LAST_NAME = os.getenv(
    "SEED_SUPER_ADMIN_LAST_NAME",
    "Admin",
)

SUPER_ADMIN_EMAIL = os.getenv(
    "SEED_SUPER_ADMIN_EMAIL",
    "superadmin@nutriomeals.com",
).strip().lower()

SUPER_ADMIN_PHONE = os.getenv(
    "SEED_SUPER_ADMIN_PHONE",
    "+966500000001",
)

SUPER_ADMIN_PASSWORD = os.getenv(
    "SEED_SUPER_ADMIN_PASSWORD",
)


ADMIN_FIRST_NAME = os.getenv(
    "SEED_ADMIN_FIRST_NAME",
    "System",
)

ADMIN_LAST_NAME = os.getenv(
    "SEED_ADMIN_LAST_NAME",
    "Admin",
)

ADMIN_EMAIL = os.getenv(
    "SEED_ADMIN_EMAIL",
    "admin@nutriomeals.com",
).strip().lower()

ADMIN_PHONE = os.getenv(
    "SEED_ADMIN_PHONE",
    "+966500000002",
)

ADMIN_PASSWORD = os.getenv(
    "SEED_ADMIN_PASSWORD",
)

def validate_environment() -> None:
    missing_variables = []

    if not SUPER_ADMIN_PASSWORD:
        missing_variables.append(
            "SEED_SUPER_ADMIN_PASSWORD"
        )

    if not ADMIN_PASSWORD:
        missing_variables.append(
            "SEED_ADMIN_PASSWORD"
        )

    if missing_variables:
        variables = ", ".join(missing_variables)

        raise RuntimeError(
            "Missing required environment variables: "
            f"{variables}"
        )

    if len(SUPER_ADMIN_PASSWORD) < 8:
        raise RuntimeError(
            "SEED_SUPER_ADMIN_PASSWORD must contain "
            "at least 8 characters."
        )

    if len(ADMIN_PASSWORD) < 8:
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD must contain "
            "at least 8 characters."
        )

    if SUPER_ADMIN_EMAIL == ADMIN_EMAIL:
        raise RuntimeError(
            "Super Admin and Admin must use different emails."
        )

    if SUPER_ADMIN_PHONE == ADMIN_PHONE:
        raise RuntimeError(
            "Super Admin and Admin must use different phone numbers."
        )

def get_user_by_email(
    db: Session,
    email: str,
) -> User | None:
    return (
        db.query(User)
        .filter(
            User.email == email.strip().lower()
        )
        .first()
    )


def get_user_by_phone(
    db: Session,
    phone: str,
) -> User | None:
    return (
        db.query(User)
        .filter(
            User.phone == phone
        )
        .first()
    )


def create_or_update_admin_user(
    db: Session,
    *,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    password: str,
    role: UserRole,
) -> tuple[User, bool]:
    normalized_email = email.strip().lower()

    user = get_user_by_email(
        db=db,
        email=normalized_email,
    )

    phone_owner = get_user_by_phone(
        db=db,
        phone=phone,
    )

    if (
        phone_owner is not None
        and (
            user is None
            or phone_owner.id != user.id
        )
    ):
        raise RuntimeError(
            f"Phone number {phone} is already used by "
            f"another account: {phone_owner.email}"
        )

    created = False

    if user is None:
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=normalized_email,
            phone=phone,
            hashed_password=hash_password(
                password
            ),
            role=role,
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow(),
        )

        db.add(user)
        created = True

    else:
        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone
        user.role = role
        user.is_active = True
        user.is_verified = True

        # The seed resets the admin password to the value
        # configured in the environment file.
        user.hashed_password = hash_password(
            password
        )

    db.commit()
    db.refresh(user)

    return user, created

def seed_admin_users() -> None:
    validate_environment()

    # Alembic should normally create production tables.
    # This line only ensures registered metadata exists.
    Base.metadata.create_all(
        bind=engine
    )

    db = SessionLocal()

    try:
        super_admin, super_admin_created = (
            create_or_update_admin_user(
                db=db,
                first_name=SUPER_ADMIN_FIRST_NAME,
                last_name=SUPER_ADMIN_LAST_NAME,
                email=SUPER_ADMIN_EMAIL,
                phone=SUPER_ADMIN_PHONE,
                password=SUPER_ADMIN_PASSWORD,
                role=UserRole.SUPER_ADMIN,
            )
        )

        admin, admin_created = (
            create_or_update_admin_user(
                db=db,
                first_name=ADMIN_FIRST_NAME,
                last_name=ADMIN_LAST_NAME,
                email=ADMIN_EMAIL,
                phone=ADMIN_PHONE,
                password=ADMIN_PASSWORD,
                role=UserRole.ADMIN,
            )
        )

        print("")
        print("==========================================")
        print("NutrioMeals production admin seed complete")
        print("==========================================")
        print("")

        print(
            "Super Admin:",
            "created"
            if super_admin_created
            else "updated",
        )
        print(
            f"  ID: {super_admin.id}"
        )
        print(
            f"  Email: {super_admin.email}"
        )
        print(
            f"  Role: {super_admin.role.value}"
        )
        print("")

        print(
            "Admin:",
            "created"
            if admin_created
            else "updated",
        )
        print(
            f"  ID: {admin.id}"
        )
        print(
            f"  Email: {admin.email}"
        )
        print(
            f"  Role: {admin.role.value}"
        )
        print("")

        print(
            "No mock customers, subscriptions, meals, "
            "plans, orders or payments were created."
        )
        print("")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_admin_users()