# myapp/chat_store.py

from db.database import SessionLocal, ChatHistory, User
import csv
from datetime import datetime

CSV_FILE_PATH = "chat_logs.csv"

def save_chat_history(user_id: int, question: str, answer: str):
    db = SessionLocal()
    try:
        chat = ChatHistory(user_id=user_id, question=question, answer=answer)
        db.add(chat)
        db.commit()

        with open(CSV_FILE_PATH, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([
                user_id,
                question,
                answer,
                datetime.utcnow().isoformat()
            ])

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
        # Reverse for chronological order
        pairs = []
        for chat in reversed(chats):
            pairs.append({"role": "user", "content": chat.question})
            pairs.append({"role": "assistant", "content": chat.answer})
        return pairs
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
