import os
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, Header
import hashlib

# 🔐 Secret settings
SECRET_KEY = os.getenv("C7UaOaJRMf5ksM0iQyw7ioTudsjomjfy85ZSADGDBic" ) # Replace with env var in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# In-memory store (replace with DB later)
users_db = {}

# --- Helper: Password hashing ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# --- Register a new user ---
def register_user(username: str, password: str) -> bool:
    if username in users_db:
        return False
    users_db[username] = hash_password(password)
    return True

# --- Authenticate and return token ---
def authenticate_user(username: str, password: str) -> str | None:
    if username not in users_db:
        return None
    hashed = hash_password(password)
    if users_db[username] != hashed:
        return None
    return create_token(user_id=username)

# --- Create JWT token ---
def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

# --- Verify JWT token from headers ---
def verify_token(token: str = Header(...)) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token invalid")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalid")