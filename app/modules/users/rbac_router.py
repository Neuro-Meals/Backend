from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.users.rbac_models import Role, Permission, UserRoleLink, RolePermission
from app.modules.users.rbac_schemas import (
    RoleCreate,
    PermissionCreate,
    AssignRoleRequest,
    AssignPermissionRequest,
)

router = APIRouter(prefix="/rbac", tags=["Roles & Permissions"])


def require_super_admin(current_user: User = Depends(get_current_user)):
    if current_user.role.value != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admin can access this")
    return current_user


@router.post("/roles")
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    exists = db.query(Role).filter(Role.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail="Role already exists")

    role = Role(name=payload.name, description=payload.description)
    db.add(role)
    db.commit()
    db.refresh(role)

    return role


@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    return db.query(Role).order_by(Role.id.desc()).all()


@router.post("/permissions")
def create_permission(
    payload: PermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    exists = db.query(Permission).filter(Permission.code == payload.code).first()
    if exists:
        raise HTTPException(status_code=400, detail="Permission already exists")

    permission = Permission(code=payload.code, description=payload.description)
    db.add(permission)
    db.commit()
    db.refresh(permission)

    return permission


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    return db.query(Permission).order_by(Permission.id.desc()).all()


@router.post("/assign-role")
def assign_role_to_user(
    payload: AssignRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    exists = db.query(UserRoleLink).filter(
        UserRoleLink.user_id == payload.user_id,
        UserRoleLink.role_id == payload.role_id,
    ).first()

    if exists:
        return {"message": "Role already assigned to user"}

    link = UserRoleLink(user_id=payload.user_id, role_id=payload.role_id)
    db.add(link)
    db.commit()

    return {"message": "Role assigned successfully"}


@router.post("/assign-permission")
def assign_permission_to_role(
    payload: AssignPermissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    exists = db.query(RolePermission).filter(
        RolePermission.role_id == payload.role_id,
        RolePermission.permission_id == payload.permission_id,
    ).first()

    if exists:
        return {"message": "Permission already assigned to role"}

    link = RolePermission(
        role_id=payload.role_id,
        permission_id=payload.permission_id,
    )
    db.add(link)
    db.commit()

    return {"message": "Permission assigned successfully"}