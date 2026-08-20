"""Admin-only user management, property-aware.

- superadmin: manages all users across all properties; can set role admin/user and assign property.
- admin (property admin): manages only users in their own property, role `user` only, cannot touch
  admins or superadmins.
Every route requires the admin role (enforced in main.py); finer checks are enforced here.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services import auth, properties

router = APIRouter(prefix="/api/admin", tags=["admin"])


class NewUser(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = ""
    role: str = "user"
    property_ids: Optional[list[int]] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    disabled: Optional[bool] = None
    property_ids: Optional[list[int]] = None


class PasswordReset(BaseModel):
    password: str


def _is_super(actor) -> bool:
    return actor["role"] == "superadmin"


def _can_manage(actor, target: dict) -> bool:
    """A property admin may only manage plain users within their own property."""
    if _is_super(actor):
        return True
    return target.get("role") == "user" and target.get("property_id") == actor.get("property_id")


@router.get("/users")
def list_users(actor: dict = Depends(auth.require_admin)):
    return auth.list_users(None if _is_super(actor) else actor.get("property_id"))


@router.post("/users")
def create_user(body: NewUser, actor: dict = Depends(auth.require_admin)):
    if auth.get_user(body.username.strip()):
        raise HTTPException(409, "That username already exists")
    issues = auth.password_issues(body.password)
    if issues:
        raise HTTPException(400, "Password needs: " + ", ".join(issues).lower())
    if _is_super(actor):
        role = body.role if body.role in ("admin", "user") else "user"
        pids = [p for p in (body.property_ids or []) if properties.get_property(p)]
        if not pids:
            raise HTTPException(400, "Assign at least one valid property")
    else:
        role = "user"  # property admins can only create users
        pids = [actor.get("property_id")] if actor.get("property_id") else []
    auth.create_user(body.username.strip(), body.password, role=role,
                     full_name=(body.full_name or "").strip(), property_ids=pids)
    return {"ok": True, "username": body.username.strip()}


@router.patch("/users/{username}")
def update_user(username: str, body: UserUpdate, actor: dict = Depends(auth.require_admin)):
    user = auth.get_user(username)
    if not user:
        raise HTTPException(404, "User not found")
    if not _can_manage(actor, user):
        raise HTTPException(403, "You cannot manage this user")
    new_role = body.role
    if new_role is not None:
        if not _is_super(actor) or new_role not in ("admin", "user"):
            raise HTTPException(403, "You cannot set that role")
    # Protect the last active admin/superadmin.
    demoting = (new_role == "user" and user["role"] in ("admin", "superadmin"))
    disabling = (body.disabled is True and user["role"] in ("admin", "superadmin"))
    if (demoting or disabling) and auth.admin_count() <= 1:
        raise HTTPException(400, "Cannot remove the last active administrator")
    auth.update_user(username, full_name=body.full_name, role=new_role,
                     disabled=None if body.disabled is None else int(body.disabled))
    # Property assignment (superadmin only, and not for superadmin accounts)
    if _is_super(actor) and body.property_ids is not None and user["role"] != "superadmin":
        pids = [p for p in body.property_ids if properties.get_property(p)]
        if not pids:
            raise HTTPException(400, "Assign at least one valid property")
        auth.set_user_properties(username, pids)
    return {"ok": True}


@router.post("/users/{username}/reset-password")
def reset_password(username: str, body: PasswordReset, actor: dict = Depends(auth.require_admin)):
    user = auth.get_user(username)
    if not user:
        raise HTTPException(404, "User not found")
    if not _can_manage(actor, user):
        raise HTTPException(403, "You cannot manage this user")
    issues = auth.password_issues(body.password)
    if issues:
        raise HTTPException(400, "Password needs: " + ", ".join(issues).lower())
    auth.set_password(username, body.password)
    return {"ok": True}


@router.delete("/users/{username}")
def delete_user(username: str, actor: dict = Depends(auth.require_admin)):
    user = auth.get_user(username)
    if not user:
        raise HTTPException(404, "User not found")
    if username == actor["username"]:
        raise HTTPException(400, "You cannot delete your own account")
    if not _can_manage(actor, user):
        raise HTTPException(403, "You cannot manage this user")
    if user["role"] in ("admin", "superadmin") and auth.admin_count() <= 1:
        raise HTTPException(400, "Cannot delete the last active administrator")
    auth.delete_user(username)
    return {"ok": True}
