# memory_store.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from myapp.database import Base
from myapp.llm_core import _chat_once

  # or your existing declarative_base()

class Memory(Base):
    __tablename__ = "memory"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    topic = Column(String(100))
    summary = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)



def summarize_conversation(history_blocks: str) -> str:
    prompt = (
        "Summarize the key topics discussed in the following conversation between a user and an assistant. "
        "Be concise and avoid repeating anything irrelevant.\n\n"
        + history_blocks
    )

    messages = [
        {"role": "system", "content": "You are a helpful assistant that summarizes past chat sessions."},
        {"role": "user", "content": prompt}
    ]

    return _chat_once(messages, max_tokens=200)

from myapp.database import SessionLocal

def save_user_memory(user_id: int, topic: str, history_blocks: str):
    summary = summarize_conversation(history_blocks)
    db = SessionLocal()

    memory = Memory(
        user_id=user_id,
        topic=topic,
        summary=summary
    )

    db.add(memory)
    db.commit()
    db.close()

    print(f"✅ Saved memory for user {user_id}: {topic}")

