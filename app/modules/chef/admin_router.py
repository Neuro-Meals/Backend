import logging
import os
import smtplib
from email.message import EmailMessage

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.database import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.chef.admin_schemas import (
    AssignChefRoleRequest,
    ChefCreate,
    ChefResponse,
    ChefUpdate,
)
from app.modules.users.models import User, UserRole
from app.modules.users.service import (
    get_user_by_email,
    get_user_by_phone,
    normalize_phone,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/admin/chefs",
    tags=["Admin Chef Management"],
)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

EMAIL_FROM = os.getenv(
    "EMAIL_FROM",
    SMTP_USERNAME or "no-reply@nutriomeals.com",
)

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "https://nutriomeals.com",
).rstrip("/")

CHEF_LOGIN_URL = os.getenv(
    "CHEF_LOGIN_URL",
    f"{FRONTEND_URL}/login",
)

def send_email_message(
    recipient: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    """
    Send an email through SMTP.

    This function is designed for FastAPI BackgroundTasks.
    Email failures are logged and do not roll back database changes.
    """

    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.error(
            "Email was not sent to %s because SMTP_USERNAME or "
            "SMTP_PASSWORD is missing.",
            recipient,
        )
        return False

    message = EmailMessage()

    message["Subject"] = subject
    message["From"] = EMAIL_FROM
    message["To"] = recipient

    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT,
            timeout=30,
        ) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()

            smtp.login(
                SMTP_USERNAME,
                SMTP_PASSWORD,
            )

            smtp.send_message(message)

        logger.info(
            "Email successfully sent to %s",
            recipient,
        )

        return True

    except Exception:
        logger.exception(
            "Failed to send email to %s",
            recipient,
        )

        return False


def send_chef_welcome_email(
    recipient_email: str,
    first_name: str,
    temporary_password: str,
) -> None:
    subject = "Welcome to NutrioMeals – Your Chef Account"

    text_body = f"""
Hello {first_name},

Your NutrioMeals Chef account has been created successfully.

Login information:

Email: {recipient_email}
Temporary password: {temporary_password}

Login here:
{CHEF_LOGIN_URL}

For security, please change your temporary password immediately after
your first login.

Your account is already verified and active.

Regards,
NutrioMeals Team
""".strip()

    html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
</head>

<body
    style="
        margin: 0;
        padding: 0;
        background-color: #f4f6f8;
        font-family: Arial, Helvetica, sans-serif;
        color: #1f2937;
    "
>
    <table
        width="100%"
        cellpadding="0"
        cellspacing="0"
        style="padding: 30px 15px;"
    >
        <tr>
            <td align="center">

                <table
                    width="100%"
                    cellpadding="0"
                    cellspacing="0"
                    style="
                        max-width: 620px;
                        background-color: #ffffff;
                        border-radius: 12px;
                        overflow: hidden;
                        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.08);
                    "
                >
                    <tr>
                        <td
                            style="
                                padding: 28px;
                                background-color: #166534;
                                color: #ffffff;
                                text-align: center;
                            "
                        >
                            <h1
                                style="
                                    margin: 0;
                                    font-size: 26px;
                                "
                            >
                                Welcome to NutrioMeals
                            </h1>

                            <p
                                style="
                                    margin: 8px 0 0;
                                    font-size: 15px;
                                "
                            >
                                Your Chef account is ready
                            </p>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 32px;">
                            <p style="font-size: 16px;">
                                Hello <strong>{first_name}</strong>,
                            </p>

                            <p
                                style="
                                    font-size: 15px;
                                    line-height: 1.7;
                                "
                            >
                                An administrator has created a
                                NutrioMeals Chef account for you.
                                Your account is already active and
                                verified.
                            </p>

                            <div
                                style="
                                    margin: 24px 0;
                                    padding: 20px;
                                    background-color: #f0fdf4;
                                    border: 1px solid #bbf7d0;
                                    border-radius: 8px;
                                "
                            >
                                <p
                                    style="
                                        margin: 0 0 12px;
                                        font-weight: bold;
                                    "
                                >
                                    Your login information
                                </p>

                                <p style="margin: 6px 0;">
                                    <strong>Email:</strong>
                                    {recipient_email}
                                </p>

                                <p style="margin: 6px 0;">
                                    <strong>Temporary password:</strong>
                                    {temporary_password}
                                </p>
                            </div>

                            <p
                                style="
                                    font-size: 14px;
                                    line-height: 1.6;
                                    color: #b45309;
                                "
                            >
                                For security, change this temporary
                                password immediately after your first
                                login.
                            </p>

                            <div
                                style="
                                    margin: 28px 0;
                                    text-align: center;
                                "
                            >
                                <a
                                    href="{CHEF_LOGIN_URL}"
                                    style="
                                        display: inline-block;
                                        padding: 13px 28px;
                                        background-color: #16a34a;
                                        color: #ffffff;
                                        text-decoration: none;
                                        border-radius: 7px;
                                        font-weight: bold;
                                    "
                                >
                                    Log in to NutrioMeals
                                </a>
                            </div>

                            <p
                                style="
                                    font-size: 14px;
                                    line-height: 1.6;
                                    color: #6b7280;
                                "
                            >
                                If the button does not work, open this
                                address in your browser:
                            </p>

                            <p
                                style="
                                    font-size: 13px;
                                    word-break: break-all;
                                    color: #166534;
                                "
                            >
                                {CHEF_LOGIN_URL}
                            </p>

                            <p
                                style="
                                    margin-top: 28px;
                                    font-size: 15px;
                                "
                            >
                                Regards,<br>
                                <strong>NutrioMeals Team</strong>
                            </p>
                        </td>
                    </tr>
                </table>

            </td>
        </tr>
    </table>
</body>
</html>
""".strip()

    send_email_message(
        recipient=recipient_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


def send_chef_role_assigned_email(
    recipient_email: str,
    first_name: str,
) -> None:
    subject = "Your NutrioMeals Account Is Now a Chef Account"

    text_body = f"""
Hello {first_name},

Your NutrioMeals account has been assigned the Chef role.

You can now sign in and access the Chef dashboard.

Login here:
{CHEF_LOGIN_URL}

Regards,
NutrioMeals Team
""".strip()

    html_body = f"""
<!DOCTYPE html>
<html lang="en">
<body
    style="
        background-color: #f4f6f8;
        font-family: Arial, Helvetica, sans-serif;
        padding: 30px 15px;
        color: #1f2937;
    "
>
    <div
        style="
            max-width: 600px;
            margin: auto;
            background-color: #ffffff;
            padding: 32px;
            border-radius: 12px;
        "
    >
        <h2 style="color: #166534;">
            Chef role assigned
        </h2>

        <p>Hello <strong>{first_name}</strong>,</p>

        <p style="line-height: 1.7;">
            An administrator has assigned the
            <strong>Chef</strong> role to your NutrioMeals account.
        </p>

        <p style="line-height: 1.7;">
            You may now sign in using your existing email and password
            and access the Chef dashboard.
        </p>

        <p style="margin: 28px 0; text-align: center;">
            <a
                href="{CHEF_LOGIN_URL}"
                style="
                    display: inline-block;
                    padding: 13px 28px;
                    background-color: #16a34a;
                    color: #ffffff;
                    text-decoration: none;
                    border-radius: 7px;
                    font-weight: bold;
                "
            >
                Open NutrioMeals
            </a>
        </p>

        <p>
            Regards,<br>
            <strong>NutrioMeals Team</strong>
        </p>
    </div>
</body>
</html>
""".strip()

    send_email_message(
        recipient=recipient_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


def send_chef_status_email(
    recipient_email: str,
    first_name: str,
    is_active: bool,
) -> None:
    if is_active:
        subject = "Your NutrioMeals Chef Account Has Been Activated"
        status_title = "Account activated"
        status_message = (
            "Your NutrioMeals Chef account has been activated. "
            "You can now sign in and use the Chef dashboard."
        )
    else:
        subject = "Your NutrioMeals Chef Account Has Been Deactivated"
        status_title = "Account deactivated"
        status_message = (
            "Your NutrioMeals Chef account has been deactivated. "
            "You will not be able to sign in until an administrator "
            "reactivates your account."
        )

    text_body = f"""
Hello {first_name},

{status_message}

Login:
{CHEF_LOGIN_URL}

Regards,
NutrioMeals Team
""".strip()

    html_body = f"""
<!DOCTYPE html>
<html lang="en">
<body
    style="
        background-color: #f4f6f8;
        font-family: Arial, Helvetica, sans-serif;
        padding: 30px 15px;
        color: #1f2937;
    "
>
    <div
        style="
            max-width: 600px;
            margin: auto;
            background-color: #ffffff;
            padding: 32px;
            border-radius: 12px;
        "
    >
        <h2 style="color: #166534;">
            {status_title}
        </h2>

        <p>Hello <strong>{first_name}</strong>,</p>

        <p style="line-height: 1.7;">
            {status_message}
        </p>

        <p>
            Regards,<br>
            <strong>NutrioMeals Team</strong>
        </p>
    </div>
</body>
</html>
""".strip()

    send_email_message(
        recipient=recipient_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


def send_chef_role_removed_email(
    recipient_email: str,
    first_name: str,
) -> None:
    subject = "Your NutrioMeals Chef Role Has Been Removed"

    text_body = f"""
Hello {first_name},

Your Chef role has been removed from your NutrioMeals account.

Your account has been changed back to a Customer account.

Regards,
NutrioMeals Team
""".strip()

    html_body = f"""
<!DOCTYPE html>
<html lang="en">
<body
    style="
        background-color: #f4f6f8;
        font-family: Arial, Helvetica, sans-serif;
        padding: 30px 15px;
        color: #1f2937;
    "
>
    <div
        style="
            max-width: 600px;
            margin: auto;
            background-color: #ffffff;
            padding: 32px;
            border-radius: 12px;
        "
    >
        <h2 style="color: #166534;">
            Chef role removed
        </h2>

        <p>Hello <strong>{first_name}</strong>,</p>

        <p style="line-height: 1.7;">
            Your Chef role has been removed from your NutrioMeals
            account. Your role is now
            <strong>Customer</strong>.
        </p>

        <p>
            Regards,<br>
            <strong>NutrioMeals Team</strong>
        </p>
    </div>
</body>
</html>
""".strip()

    send_email_message(
        recipient=recipient_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )

def chef_payload(user: User) -> dict:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": f"{user.first_name} {user.last_name}",
        "email": user.email,
        "phone": user.phone,
        "location": getattr(user, "location", None),
        "address": getattr(user, "address", None),
        "role": (
            user.role.value
            if hasattr(user.role, "value")
            else user.role
        ),
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
        "updated_at": getattr(user, "updated_at", None),
    }


def get_chef_or_404(
    db: Session,
    chef_id: int,
) -> User:
    chef = (
        db.query(User)
        .filter(
            User.id == chef_id,
            User.role == UserRole.CHEF,
        )
        .first()
    )

    if chef is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chef not found",
        )

    return chef

@router.post(
    "/",
    response_model=ChefResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_chef(
    payload: ChefCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    normalized_email = payload.email.strip().lower()
    normalized_phone = normalize_phone(payload.phone)

    if get_user_by_email(db, normalized_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    if get_user_by_phone(db, normalized_phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is already registered",
        )

    # Keep the plain password only long enough to send the welcome email.
    temporary_password = payload.password

    chef = User(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=normalized_email,
        phone=normalized_phone,
        hashed_password=hash_password(temporary_password),
        location=(
            payload.location.strip()
            if payload.location
            else None
        ),
        address=(
            payload.address.strip()
            if payload.address
            else None
        ),
        role=UserRole.CHEF,
        is_verified=True,
        is_active=True,
        gender=None,
        age=None,
        height_cm=None,
        weight_kg=None,
        fitness_goal=None,
        dietary_preference=None,
        allergies=[],
        email_otp=None,
        email_otp_expires_at=None,
    )

    db.add(chef)

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Chef could not be created because of duplicate data"
            ),
        ) from exc

    db.refresh(chef)

    # Email is queued only after the database commit succeeds.
    background_tasks.add_task(
        send_chef_welcome_email,
        recipient_email=chef.email,
        first_name=chef.first_name,
        temporary_password=temporary_password,
    )

    return chef_payload(chef)

@router.get("/")
def list_chefs(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = (
        db.query(User)
        .filter(User.role == UserRole.CHEF)
    )

    if search:
        value = f"%{search.strip()}%"

        query = query.filter(
            or_(
                User.first_name.ilike(value),
                User.last_name.ilike(value),
                User.email.ilike(value),
                User.phone.ilike(value),
                User.location.ilike(value),
            )
        )

    if is_active is not None:
        query = query.filter(
            User.is_active.is_(is_active)
        )

    total = query.count()

    chefs = (
        query.order_by(User.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": [
            chef_payload(chef)
            for chef in chefs
        ],
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (
                (total + limit - 1) // limit
                if total
                else 0
            ),
        },
    }


@router.get(
    "/{chef_id}",
    response_model=ChefResponse,
)
def get_chef(
    chef_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    chef = get_chef_or_404(
        db=db,
        chef_id=chef_id,
    )

    return chef_payload(chef)

@router.patch(
    "/{chef_id}",
    response_model=ChefResponse,
)
def update_chef(
    chef_id: int,
    payload: ChefUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    chef = get_chef_or_404(
        db=db,
        chef_id=chef_id,
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    if "email" in update_data:
        normalized_email = (
            str(update_data["email"])
            .strip()
            .lower()
        )

        existing_email = (
            db.query(User)
            .filter(
                User.email == normalized_email,
                User.id != chef.id,
            )
            .first()
        )

        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already used by another user",
            )

        chef.email = normalized_email

    if "phone" in update_data:
        normalized_phone = normalize_phone(
            update_data["phone"]
        )

        existing_phone = (
            db.query(User)
            .filter(
                User.phone == normalized_phone,
                User.id != chef.id,
            )
            .first()
        )

        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number is already used by another user",
            )

        chef.phone = normalized_phone

    if "first_name" in update_data:
        chef.first_name = (
            update_data["first_name"].strip()
        )

    if "last_name" in update_data:
        chef.last_name = (
            update_data["last_name"].strip()
        )

    if "location" in update_data:
        chef.location = (
            update_data["location"].strip()
            if update_data["location"]
            else None
        )

    if "address" in update_data:
        chef.address = (
            update_data["address"].strip()
            if update_data["address"]
            else None
        )

    if "is_active" in update_data:
        chef.is_active = update_data["is_active"]

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chef could not be updated",
        ) from exc

    db.refresh(chef)

    return chef_payload(chef)

@router.patch(
    "/{chef_id}/activate",
    response_model=ChefResponse,
)
def activate_chef(
    chef_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    chef = get_chef_or_404(
        db=db,
        chef_id=chef_id,
    )

    if chef.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chef is already active",
        )

    chef.is_active = True

    db.commit()
    db.refresh(chef)

    background_tasks.add_task(
        send_chef_status_email,
        recipient_email=chef.email,
        first_name=chef.first_name,
        is_active=True,
    )

    return chef_payload(chef)

@router.patch(
    "/{chef_id}/deactivate",
    response_model=ChefResponse,
)
def deactivate_chef(
    chef_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    chef = get_chef_or_404(
        db=db,
        chef_id=chef_id,
    )

    if not chef.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chef is already inactive",
        )

    chef.is_active = False

    db.commit()
    db.refresh(chef)

    background_tasks.add_task(
        send_chef_status_email,
        recipient_email=chef.email,
        first_name=chef.first_name,
        is_active=False,
    )

    return chef_payload(chef)

@router.post(
    "/assign-existing-user",
    response_model=ChefResponse,
)
def assign_existing_user_as_chef(
    payload: AssignChefRoleRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    user = (
        db.query(User)
        .filter(User.id == payload.user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.role == UserRole.CHEF:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a chef",
        )

    if user.role in {
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An administrator cannot be converted into a chef",
        )

    user.role = UserRole.CHEF
    user.is_active = True

    db.commit()
    db.refresh(user)

    background_tasks.add_task(
        send_chef_role_assigned_email,
        recipient_email=user.email,
        first_name=user.first_name,
    )

    return chef_payload(user)

@router.patch(
    "/{chef_id}/remove-role",
    response_model=ChefResponse,
)
def remove_chef_role(
    chef_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    chef = get_chef_or_404(
        db=db,
        chef_id=chef_id,
    )

    chef.role = UserRole.CUSTOMER

    db.commit()
    db.refresh(chef)

    background_tasks.add_task(
        send_chef_role_removed_email,
        recipient_email=chef.email,
        first_name=chef.first_name,
    )

    response = chef_payload(chef)
    response["role"] = UserRole.CUSTOMER.value

    return response