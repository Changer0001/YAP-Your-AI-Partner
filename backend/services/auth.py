"""Authentication — local user accounts, password hashing, and signed session tokens.

Uses only the Python standard library (scrypt for passwords, HMAC-signed tokens) so there are no
extra compiled dependencies. Single-user to start; the `role` column lets RBAC grow later.

Security notes:
- Passwords are stored as scrypt(salt, password); the plaintext is never stored or logged.
- The signing secret is generated once and kept in `data/secret.key` (chmod 600), never in git.
- Tokens are stateless, signed, and expiring; a 401 clears them client-side.
"""
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Header, HTTPException

from backend.config import settings

_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)
TOKEN_TTL_SECONDS = int(os.getenv("SESSION_TTL_HOURS", "12")) * 3600


# --------------------------------------------------------------------------- secret
def _secret() -> bytes:
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


_SECRET = _secret()


# --------------------------------------------------------------------------- passwords
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
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                created_at TEXT
            )
            """
        )


def user_count() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_user(username: str, password: str, role: str = "admin") -> None:
    salt, pwhash = hash_password(password)
    with _conn() as conn:
        conn.execute(
            "INSERT INTO users (username, salt, password_hash, role, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, salt, pwhash, role,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def get_user(username: str) -> Optional[dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def authenticate(username: str, password: str) -> Optional[dict[str, Any]]:
    user = get_user(username)
    if not user or not verify_password(password, user["salt"], user["password_hash"]):
        return None
    return {"username": user["username"], "role": user["role"]}


# --------------------------------------------------------------------------- login throttle
_attempts: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 5
_WINDOW = 300  # seconds


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


# --------------------------------------------------------------------------- dependency
def require_auth(authorization: str = Header(default="")) -> dict[str, Any]:
    """FastAPI dependency: require a valid Bearer token; return the user claims."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentication required")
    claims = verify_token(authorization.split(" ", 1)[1].strip())
    if not claims:
        raise HTTPException(401, "Invalid or expired session")
    return {"username": claims.get("sub"), "role": claims.get("role", "user")}


init_db()
