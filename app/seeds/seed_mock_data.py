from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.modules.users.models import User, UserRole


# ============================================================
# LOAD SEED CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_ENV_FILE = PROJECT_ROOT / ".env.seed"

seed_config = dotenv_values(SEED_ENV_FILE)


def get_required_setting(name: str) -> str:
    value = seed_config.get(name)

    if value is None or not str(value).strip():
        raise RuntimeError(
            f"Missing required setting '{name}' in {SEED_ENV_FILE}"
        )

    return str(value).strip()


SUPER_ADMIN_FIRST_NAME = seed_config.get(
    "SEED_SUPER_ADMIN_FIRST_NAME",
    "Super",
).strip()

SUPER_ADMIN_LAST_NAME = seed_config.get(
    "SEED_SUPER_ADMIN_LAST_NAME",
    "Admin",
).strip()

SUPER_ADMIN_EMAIL = get_required_setting(
    "SEED_SUPER_ADMIN_EMAIL"
).lower()

SUPER_ADMIN_PHONE = get_required_setting(
    "SEED_SUPER_ADMIN_PHONE"
)

SUPER_ADMIN_PASSWORD = get_required_setting(
    "SEED_SUPER_ADMIN_PASSWORD"
)


ADMIN_FIRST_NAME = seed_config.get(
    "SEED_ADMIN_FIRST_NAME",
    "System",
).strip()

ADMIN_LAST_NAME = seed_config.get(
    "SEED_ADMIN_LAST_NAME",
    "Admin",
).strip()

ADMIN_EMAIL = get_required_setting(
    "SEED_ADMIN_EMAIL"
).lower()

ADMIN_PHONE = get_required_setting(
    "SEED_ADMIN_PHONE"
)

ADMIN_PASSWORD = get_required_setting(
    "SEED_ADMIN_PASSWORD"
)


# ============================================================
# VALIDATION
# ============================================================

def validate_seed_configuration() -> None:
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
            "Super Admin and Admin must use different email addresses."
        )

    if SUPER_ADMIN_PHONE == ADMIN_PHONE:
        raise RuntimeError(
            "Super Admin and Admin must use different phone numbers."
        )

    if not SUPER_ADMIN_EMAIL.endswith(
        ("@gmail.com", "@nutriomeals.com")
    ):
        print(
            "Warning: Super Admin email uses an unexpected domain:",
            SUPER_ADMIN_EMAIL,
        )

    if not ADMIN_EMAIL.endswith(
        ("@gmail.com", "@nutriomeals.com")
    ):
        print(
            "Warning: Admin email uses an unexpected domain:",
            ADMIN_EMAIL,
        )


# ============================================================
# DATABASE QUERIES
# ============================================================

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
    return (
        db.query(User)
        .filter(User.phone == phone.strip())
        .first()
    )


# ============================================================
# CREATE OR UPDATE ADMIN USER
# ============================================================

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
    normalized_phone = phone.strip()

    user = get_user_by_email(
        db=db,
        email=normalized_email,
    )

    phone_owner = get_user_by_phone(
        db=db,
        phone=normalized_phone,
    )

    if (
        phone_owner is not None
        and (
            user is None
            or phone_owner.id != user.id
        )
    ):
        raise RuntimeError(
            f"Phone number {normalized_phone} is already used "
            f"by another account: {phone_owner.email}"
        )

    created = user is None

    if created:
        user = User(
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=normalized_email,
            phone=normalized_phone,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow(),
        )

        db.add(user)

    else:
        user.first_name = first_name.strip()
        user.last_name = last_name.strip()
        user.phone = normalized_phone
        user.role = role
        user.is_active = True
        user.is_verified = True

        # Running the seed again resets this account's password
        # to the value stored inside .env.seed.
        user.hashed_password = hash_password(password)

    db.flush()

    return user, created


# ============================================================
# MAIN SEED
# ============================================================

def seed_admin_users() -> None:
    validate_seed_configuration()

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

        admin, admin_created = create_or_update_admin_user(
            db=db,
            first_name=ADMIN_FIRST_NAME,
            last_name=ADMIN_LAST_NAME,
            email=ADMIN_EMAIL,
            phone=ADMIN_PHONE,
            password=ADMIN_PASSWORD,
            role=UserRole.ADMIN,
        )

        db.commit()

        db.refresh(super_admin)
        db.refresh(admin)

        print()
        print("==========================================")
        print("NutrioMeals production admin seed complete")
        print("==========================================")
        print()

        print(
            "Super Admin:",
            "created" if super_admin_created else "updated",
        )
        print(f"  ID: {super_admin.id}")
        print(f"  Name: {super_admin.first_name} {super_admin.last_name}")
        print(f"  Email: {super_admin.email}")
        print(f"  Phone: {super_admin.phone}")
        print(f"  Role: {super_admin.role.value}")
        print()

        print(
            "Admin:",
            "created" if admin_created else "updated",
        )
        print(f"  ID: {admin.id}")
        print(f"  Name: {admin.first_name} {admin.last_name}")
        print(f"  Email: {admin.email}")
        print(f"  Phone: {admin.phone}")
        print(f"  Role: {admin.role.value}")
        print()

        print(
            "No customers, chefs, drivers, meals, plans, "
            "subscriptions, payments, notifications or orders "
            "were created."
        )
        print()

    except Exception as exc:
        db.rollback()

        print()
        print("Admin seed failed.")
        print(f"Reason: {exc}")
        print()

        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_admin_users()