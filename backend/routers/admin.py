"""Admin-only endpoints — user management. Every route requires the admin role (enforced by the
`require_admin` dependency applied at include time in main.py). Never rely on the frontend for this.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services import auth

router = APIRouter(prefix="/api/admin", tags=["admin"])


class NewUser(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = ""
    role: str = "user"


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    disabled: Optional[bool] = None


class PasswordReset(BaseModel):
    password: str


@router.get("/users")
def list_users():
    return auth.list_users()


@router.post("/users")
def create_user(body: NewUser):
    if body.role not in ("admin", "user"):
        raise HTTPException(400, "Role must be admin or user")
    if auth.get_user(body.username.strip()):
        raise HTTPException(409, "That username already exists")
    issues = auth.password_issues(body.password)
    if issues:
        raise HTTPException(400, "Password needs: " + ", ".join(issues).lower())
    auth.create_user(body.username.strip(), body.password, role=body.role,
                     full_name=(body.full_name or "").strip())
    return auth.get_user(body.username.strip()) and {"ok": True, "username": body.username.strip()}


@router.patch("/users/{username}")
def update_user(username: str, body: UserUpdate, admin=Depends(auth.require_admin)):
    user = auth.get_user(username)
    if not user:
        raise HTTPException(404, "User not found")
    if body.role is not None and body.role not in ("admin", "user"):
        raise HTTPException(400, "Role must be admin or user")
    # Don't let an admin lock everyone out by demoting/disabling the last active admin.
    demoting = (body.role == "user" and user["role"] == "admin")
    disabling = (body.disabled is True and user["role"] == "admin")
    if (demoting or disabling) and auth.admin_count() <= 1:
        raise HTTPException(400, "Cannot remove the last active administrator")
    auth.update_user(username, full_name=body.full_name, role=body.role,
                     disabled=None if body.disabled is None else int(body.disabled))
    return {"ok": True}


@router.post("/users/{username}/reset-password")
def reset_password(username: str, body: PasswordReset):
    if not auth.get_user(username):
        raise HTTPException(404, "User not found")
    issues = auth.password_issues(body.password)
    if issues:
        raise HTTPException(400, "Password needs: " + ", ".join(issues).lower())
    auth.set_password(username, body.password)
    return {"ok": True}


@router.delete("/users/{username}")
def delete_user(username: str, admin=Depends(auth.require_admin)):
    user = auth.get_user(username)
    if not user:
        raise HTTPException(404, "User not found")
    if username == admin["username"]:
        raise HTTPException(400, "You cannot delete your own account")
    if user["role"] == "admin" and auth.admin_count() <= 1:
        raise HTTPException(400, "Cannot delete the last active administrator")
    auth.delete_user(username)
    return {"ok": True}
