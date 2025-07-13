# myapp/auth.py

from jose import JWTError, jwt
from fastapi import HTTPException, Header, Depends
from sqlalchemy.orm import Session
from .database import SessionLocal, User
import hashlib
import os
from datetime import datetime, timedelta
from .database import get_db


SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# --- Utility ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# --- Register ---
def register_user(username: str, password: str, db: Session) -> bool:
    if db.query(User).filter(User.username == username).first():
        return False
    new_user = User(username=username, hashed_password=hash_password(password))
    db.add(new_user)
    db.commit()
    return True

# --- Authenticate ---
def authenticate_user(username: str, password: str, db: Session) -> str:
    user = db.query(User).filter(User.username == username).first()
    if not user or user.hashed_password != hash_password(password):
        return None
    return create_token(user.username)

# --- Create Token ---
def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# --- Verify Token ---
def verify_token(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    token = authorization.split(" ")[1]  # Extract token after "Bearer"

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
