# myapp/utils.py

from myapp.database import SessionLocal, User

def get_user_id(username: str) -> int:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError("User not found")
        return user.id
    finally:
        db.close()
