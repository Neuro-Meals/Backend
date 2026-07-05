from pydantic import BaseModel


class RoleCreate(BaseModel):
    name: str
    description: str | None = None


class PermissionCreate(BaseModel):
    code: str
    description: str | None = None


class AssignRoleRequest(BaseModel):
    user_id: int
    role_id: int


class AssignPermissionRequest(BaseModel):
    role_id: int
    permission_id: int