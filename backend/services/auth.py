"""Authentication & authorization — local accounts, roles, password policy, signed tokens.

Standard-library only (scrypt passwords, HMAC-signed tokens). Roles: `admin`, `user`.
Authorization is enforced server-side via `require_auth` / `require_admin` dependencies — the
frontend reflects permissions but never grants them.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException

from backend.config import settings

_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)
TOKEN_TTL_SECONDS = int(os.getenv("SESSION_TTL_HOURS", "12")) * 3600


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- secret
def _load_secret() -> bytes:
    path = settings.data_dir / "secret.key"
    if path.exists():
        return path.read_bytes()
    key = os.urandom(32)
    path.write_bytes(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


_SECRET = _load_secret()


# --------------------------------------------------------------------------- passwords
def password_issues(pw: str) -> list[str]:
    """Return the list of unmet password requirements (empty = valid)."""
    issues = []
    if len(pw or "") < 8:
        issues.append("At least 8 characters")
    if not re.search(r"[A-Z]", pw or ""):
        issues.append("One uppercase letter")
    if not re.search(r"[0-9]", pw or ""):
        issues.append("One number")
    if not re.search(r"[^A-Za-z0-9]", pw or ""):
        issues.append("One special character")
    return issues


def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    salt = salt or os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return salt.hex(), dk.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    try:
        dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    except Exception:
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


# --------------------------------------------------------------------------- tokens
def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _ub64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_token(payload: dict[str, Any], ttl: int = TOKEN_TTL_SECONDS) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl
    raw = _b64(json.dumps(body, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_SECRET, raw.encode(), hashlib.sha256).digest())
    return f"{raw}.{sig}"


def verify_token(token: str) -> Optional[dict[str, Any]]:
    try:
        raw, sig = token.split(".", 1)
        expected = _b64(hmac.new(_SECRET, raw.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        body = json.loads(_ub64(raw))
        if int(body.get("exp", 0)) < int(time.time()):
            return None
        return body
    except Exception:
        return None


# --------------------------------------------------------------------------- user store
def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.registry_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                full_name TEXT,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                disabled INTEGER DEFAULT 0,
                created_at TEXT,
                last_login TEXT
            )
            """
        )
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        for col, ddl in {"full_name": "TEXT", "disabled": "INTEGER DEFAULT 0",
                         "last_login": "TEXT"}.items():
            if col not in cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")


def user_count() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_user(username: str, password: str, role: str = "user",
                full_name: str = "") -> None:
    salt, pwhash = hash_password(password)
    with _conn() as conn:
        conn.execute(
            "INSERT INTO users (username, full_name, salt, password_hash, role, disabled, created_at) "
            "VALUES (?, ?, ?, ?, ?, 0, ?)",
            (username, full_name, salt, pwhash, role, _now()),
        )


def get_user(username: str) -> Optional[dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return {"username": row["username"], "full_name": row.get("full_name") or "",
            "role": row.get("role") or "user", "disabled": bool(row.get("disabled")),
            "created_at": row.get("created_at"), "last_login": row.get("last_login")}


def list_users() -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [_public(dict(r)) for r in rows]


def update_user(username: str, **fields) -> None:
    allowed = {k: v for k, v in fields.items()
               if k in ("full_name", "role", "disabled") and v is not None}
    if not allowed:
        return
    sets = ", ".join(f"{k} = :{k}" for k in allowed)
    allowed["_u"] = username
    with _conn() as conn:
        conn.execute(f"UPDATE users SET {sets} WHERE username = :_u", allowed)


def set_password(username: str, password: str) -> None:
    salt, pwhash = hash_password(password)
    with _conn() as conn:
        conn.execute("UPDATE users SET salt = ?, password_hash = ? WHERE username = ?",
                     (salt, pwhash, username))


def delete_user(username: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (username,))


def admin_count() -> int:
    with _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='admin' AND disabled=0").fetchone()[0]


def authenticate(username: str, password: str) -> Optional[dict[str, Any]]:
    user = get_user(username)
    if not user or user.get("disabled") or not verify_password(
            password, user["salt"], user["password_hash"]):
        return None
    with _conn() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE username = ?", (_now(), username))
    return _public(user)


# --------------------------------------------------------------------------- login throttle
_attempts: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 5
_WINDOW = 300


def check_throttle(key: str) -> None:
    now = time.time()
    hits = [t for t in _attempts.get(key, []) if now - t < _WINDOW]
    _attempts[key] = hits
    if len(hits) >= _MAX_ATTEMPTS:
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.")


def record_failure(key: str) -> None:
    _attempts.setdefault(key, []).append(time.time())


def clear_failures(key: str) -> None:
    _attempts.pop(key, None)


# --------------------------------------------------------------------------- dependencies
def require_auth(authorization: str = Header(default="")) -> dict[str, Any]:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentication required")
    claims = verify_token(authorization.split(" ", 1)[1].strip())
    if not claims:
        raise HTTPException(401, "Invalid or expired session")
    return {"username": claims.get("sub"), "full_name": claims.get("name", ""),
            "role": claims.get("role", "user")}


def require_admin(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(403, "Administrator access required")
    return user


def token_for(user: dict[str, Any]) -> str:
    return sign_token({"sub": user["username"], "name": user.get("full_name", ""),
                       "role": user["role"]})


init_db()
