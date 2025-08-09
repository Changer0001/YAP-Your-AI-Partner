from app.db.database import SessionLocal, User
import logging

def get_user_id(username: str) -> int:
    """
    Retrieve the user ID associated with the given username.

    Args:
        username (str): The username to look up.

    Returns:
        int: The user's ID.

    Raises:
        ValueError: If the user is not found.
        Exception: If any database-related error occurs.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            logging.warning("❌ User not found: %s", username)
            raise ValueError(f"User '{username}' not found in the database.")
        
        logging.debug("🔍 Found user ID %d for username '%s'", user.id, username)
        return user.id

    except Exception as e:
        logging.error("⚠️ Failed to fetch user ID for '%s': %s", username, e)
        raise

    finally:
        db.close()
