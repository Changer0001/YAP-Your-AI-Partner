"""Authentication endpoints (public).

Flow: on first run there are no users -> the UI shows a one-time "create admin" screen
(`/setup`). After that, `/login` issues a signed session token. `/me` validates a token.
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.services import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str
    password: str


@router.get("/status")
def status(authorization: str = Header(default="")):
    """Public: does the app need first-run setup, and is the caller authenticated?"""
    authed = False
    user = None
    if authorization.lower().startswith("bearer "):
        claims = auth.verify_token(authorization.split(" ", 1)[1].strip())
        if claims:
            authed = True
            user = {"username": claims.get("sub"), "role": claims.get("role")}
    return {"needs_setup": auth.user_count() == 0, "authenticated": authed, "user": user}


@router.post("/setup")
def setup(creds: Credentials):
    """Create the first admin account. Allowed only when no users exist yet."""
    if auth.user_count() > 0:
        raise HTTPException(409, "Setup already completed")
    username = creds.username.strip()
    if len(username) < 3 or len(creds.password) < 8:
        raise HTTPException(400, "Username min 3 chars, password min 8 chars")
    auth.create_user(username, creds.password, role="admin")
    token = auth.sign_token({"sub": username, "role": "admin"})
    return {"token": token, "user": {"username": username, "role": "admin"}}


@router.post("/login")
def login(creds: Credentials):
    key = creds.username.strip().lower()
    auth.check_throttle(key)
    user = auth.authenticate(creds.username.strip(), creds.password)
    if not user:
        auth.record_failure(key)
        raise HTTPException(401, "Invalid username or password")
    auth.clear_failures(key)
    token = auth.sign_token({"sub": user["username"], "role": user["role"]})
    return {"token": token, "user": user}


@router.get("/me")
def me(authorization: str = Header(default="")):
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentication required")
    claims = auth.verify_token(authorization.split(" ", 1)[1].strip())
    if not claims:
        raise HTTPException(401, "Invalid or expired session")
    return {"username": claims.get("sub"), "role": claims.get("role")}
