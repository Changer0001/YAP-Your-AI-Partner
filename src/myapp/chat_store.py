# myapp/chat_store.py

from myapp.database import SessionLocal, ChatHistory, User

def save_chat_history(user_id: int, question: str, answer: str):
    db = SessionLocal()
    try:
        chat = ChatHistory(user_id=user_id, question=question, answer=answer)
        db.add(chat)
        db.commit()
    finally:
        db.close()


def get_user_history(user_id: int):
    db = SessionLocal()
    try:
        history = (
            db.query(ChatHistory)
            .filter(ChatHistory.user_id == user_id)
            .order_by(ChatHistory.timestamp.desc())
            .all()
        )
        return [
            {
                "question": chat.question,
                "answer": chat.answer,
                "timestamp": chat.timestamp.isoformat()
            }
            for chat in history
        ]
    finally:
        db.close()
