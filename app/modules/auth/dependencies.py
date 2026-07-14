from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.database import get_db
from app.modules.users.models import User, UserRole
from app.modules.users.service import get_user_by_id
from jose import JWTError, jwt

from app.core.config import settings

optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=False,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(token)

    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = get_user_by_id(db, int(payload["sub"]))

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


def require_roles(*roles: UserRole):
    def checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return current_user

    return checker

def get_optional_current_user(
    token: str | None = Depends(optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Return the authenticated user when a valid token is supplied.

    Return None when:
    - no Authorization header was supplied;
    - the token is invalid;
    - the user no longer exists.

    This dependency never blocks anonymous requests.
    """

    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        subject = payload.get("sub")

        if subject is None:
            return None

        user_id = int(subject)

    except (JWTError, TypeError, ValueError):
        return None

    return (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )