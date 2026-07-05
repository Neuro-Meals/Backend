from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.users.rbac_models import (
    UserRoleLink,
    RolePermission,
    Permission,
)


def get_user_permissions(db: Session, user: User) -> list[str]:

    permissions = (
        db.query(Permission.code)
        .join(RolePermission, Permission.id == RolePermission.permission_id)
        .join(UserRoleLink, UserRoleLink.role_id == RolePermission.role_id)
        .filter(UserRoleLink.user_id == user.id)
        .all()
    )

    return [p[0] for p in permissions]