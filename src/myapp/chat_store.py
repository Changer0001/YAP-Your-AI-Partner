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

# myapp/chat_store.py

def get_recent_history(user_id: int, limit: int = 5):
    db = SessionLocal()
    try:
        chats = (
            db.query(ChatHistory)
            .filter(ChatHistory.user_id == user_id)
            .order_by(ChatHistory.timestamp.desc())
            .limit(limit)
            .all()
        )
         # Reverse to get oldest-to-newest
        return "\n".join(reversed([
         f"🧑 Q: {chat.question}\n🤖 A: {chat.answer}"
        for chat in chats
        ]))
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
