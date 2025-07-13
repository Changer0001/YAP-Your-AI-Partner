from myapp.database import SessionLocal, User
import logging

def get_user_id(username: str) -> int:
    """Retrieve user ID by username from the database."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            logging.warning("User not found: %s", username)
            raise ValueError(f"User '{username}' not found in the database.")
        logging.debug("🔍 Found user ID %d for username '%s'", user.id, username)
        return user.id
    finally:
        db.close()
