import os
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, Header
import hashlib
from typing import Optional
from fastapi import Request
import json

# 🔐 Secret settings
SECRET_KEY = os.getenv("SECRET_KEY", "C7UaOaJRMf5ksM0iQyw7ioTudsjomjfy85ZSADGDBic")  # ✅ Use env var, fallback for testing
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 6
USER_DB_FILE = "C:\\Users\\Burak\\Documents\\GitHub\\LLM_Assistance\\data\\users.json"


# 🗃 In-memory user store (replace with a database later)
# 🔁 Load users from file
def load_users():
    if os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, "r") as f:
            return json.load(f)
    return {}

# 💾 Save users to file
def save_users(users):
    with open(USER_DB_FILE, "w") as f:
        json.dump(users, f)


# --- 🔐 Helper: Password hashing ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# --- 👤 Register a new user ---
def register_user(username: str, password: str) -> bool:
    users_db = load_users()
    print("📂 Loaded users before registration:", users_db)  # Debug line
    if username in users_db:
        return False
    users_db[username] = hash_password(password)
    save_users(users_db)
    print("✅ Saved users after registration:", users_db)  # Debug line
    return True

# --- 🔑 Authenticate and return token ---
def authenticate_user(username: str, password: str) -> Optional[str]:
    users_db = load_users()
    if username not in users_db:
        return None
    hashed = hash_password(password)
    if users_db[username] != hashed:
        return None
    return create_token(user_id=username)

# --- 🪙 Create JWT token ---
def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

# --- ✅ Verify JWT token from headers ---

def verify_token(authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ")[1]
    return decode_token(token)

def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
