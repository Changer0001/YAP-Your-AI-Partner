"""Authentication endpoints (public).

- First run: `/setup` creates the first admin.
- `/register` self-service creates a regular `user` account.
- `/login` issues a signed session token. `/status` and `/me` report the caller.
- Password reset on a local, mail-less app is admin-initiated (see admin router); `/forgot` just
  returns guidance rather than pretending to send an email.
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.services import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    setup_key: Optional[str] = None


def _issue(user: dict):
    return {"token": auth.token_for(user), "user": user}


def _validate(username: str, password: str):
    if len(username.strip()) < 3:
        raise HTTPException(400, "Username/email must be at least 3 characters")
    issues = auth.password_issues(password)
    if issues:
        raise HTTPException(400, "Password needs: " + ", ".join(issues).lower())


def _session_user(authorization: str):
    u = auth.user_from_bearer(authorization)
    if not u:
        return None
    return {"username": u["username"], "full_name": u["full_name"], "role": u["role"],
            "property_id": u["property_id"], "property_ids": u.get("property_ids", [])}


@router.get("/status")
def status(authorization: str = Header(default="")):
    user = _session_user(authorization)
    return {"needs_setup": auth.user_count() == 0, "authenticated": bool(user), "user": user,
            "allow_registration": settings.allow_registration}


@router.post("/setup")
def setup(creds: Credentials):
    if auth.user_count() > 0:
        raise HTTPException(409, "Setup already completed")
    if not auth.verify_setup_key(creds.setup_key or ""):
        raise HTTPException(403, "Invalid setup key. It is shown in the server terminal on first "
                                 "run and saved in data/setup_key.txt.")
    _validate(creds.username, creds.password)
    auth.create_user(creds.username.strip(), creds.password, role="superadmin",
                     full_name=(creds.full_name or "").strip())
    auth.clear_setup_key()
    return _issue({"username": creds.username.strip(),
                   "full_name": (creds.full_name or "").strip(), "role": "superadmin",
                   "property_id": None})


@router.post("/register")
def register(creds: Credentials):
    """Self-service registration -> regular `user`. Disabled unless ALLOW_REGISTRATION is set."""
    if not settings.allow_registration:
        raise HTTPException(403, "Self-registration is disabled. Ask an administrator for an account.")
    if auth.user_count() == 0:
        raise HTTPException(400, "Create the first admin account via setup first")
    _validate(creds.username, creds.password)
    if auth.get_user(creds.username.strip()):
        raise HTTPException(409, "An account with that email already exists")
    auth.create_user(creds.username.strip(), creds.password, role="user",
                     full_name=(creds.full_name or "").strip())
    return _issue({"username": creds.username.strip(),
                   "full_name": (creds.full_name or "").strip(), "role": "user"})


@router.post("/login")
def login(creds: Credentials):
    key = creds.username.strip().lower()
    auth.check_throttle(key)
    user = auth.authenticate(creds.username.strip(), creds.password)
    if not user:
        auth.record_failure(key)
        raise HTTPException(401, "Invalid email or password")
    auth.clear_failures(key)
    return _issue(user)


@router.get("/forgot")
def forgot():
    # Local, mail-less deployment: no email reset. Be honest about the real path.
    return {"message": "This is a local application with no email server. Ask an administrator to "
                       "reset your password from the Users page."}


@router.get("/me")
def me(authorization: str = Header(default="")):
    user = _session_user(authorization)
    if not user:
        raise HTTPException(401, "Invalid or expired session")
    return user
