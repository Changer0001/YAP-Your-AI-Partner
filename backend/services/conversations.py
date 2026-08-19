"""Conversation memory — persistent, per-user conversations & messages.

Isolation is mandatory and enforced here: every read/write takes the owner's `user_id` and filters
on it, so one user can never touch another user's conversation. This is separate from the Knowledge
Base — conversation history is "what YAP and the user discussed", not indexed knowledge.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.config import settings

ROLES = {"system", "user", "assistant", "tool"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.data_dir / "conversations.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                summary TEXT,
                created_at TEXT,
                updated_at TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                timestamp TEXT
            )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, timestamp)")


# ------------------------------------------------------------------ conversations
def create(user_id: str, title: str = "New conversation") -> dict[str, Any]:
    cid = uuid.uuid4().hex
    now = _now()
    with _conn() as conn:
        conn.execute("INSERT INTO conversations (id, user_id, title, summary, created_at, updated_at) "
                     "VALUES (?, ?, ?, '', ?, ?)", (cid, user_id, title, now, now))
    return {"id": cid, "user_id": user_id, "title": title, "summary": "",
            "created_at": now, "updated_at": now}


def get(conversation_id: str, user_id: str) -> Optional[dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ? AND user_id = ?",
                           (conversation_id, user_id)).fetchone()
    return dict(row) if row else None


def list_for(user_id: str) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute("SELECT id, title, created_at, updated_at FROM conversations "
                            "WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def rename(conversation_id: str, user_id: str, title: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("UPDATE conversations SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                           (title.strip()[:120] or "Conversation", _now(), conversation_id, user_id))
        return cur.rowcount > 0


def set_title(conversation_id: str, user_id: str, title: str) -> None:
    rename(conversation_id, user_id, title)


def set_summary(conversation_id: str, user_id: str, summary: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE conversations SET summary = ? WHERE id = ? AND user_id = ?",
                     (summary, conversation_id, user_id))


def delete(conversation_id: str, user_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?",
                           (conversation_id, user_id))
        conn.execute("DELETE FROM messages WHERE conversation_id = ? AND user_id = ?",
                     (conversation_id, user_id))
        return cur.rowcount > 0


# ------------------------------------------------------------------ messages
def add_message(conversation_id: str, user_id: str, role: str, content: str,
                metadata: Optional[dict] = None) -> Optional[dict[str, Any]]:
    if role not in ROLES:
        role = "user"
    if not get(conversation_id, user_id):  # ownership check
        return None
    mid = uuid.uuid4().hex
    ts = _now()
    with _conn() as conn:
        conn.execute("INSERT INTO messages (id, conversation_id, user_id, role, content, metadata, timestamp) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (mid, conversation_id, user_id, role, content,
                      json.dumps(metadata) if metadata else None, ts))
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (ts, conversation_id))
    return {"id": mid, "role": role, "content": content, "metadata": metadata, "timestamp": ts}


def messages(conversation_id: str, user_id: str, limit: Optional[int] = None) -> list[dict[str, Any]]:
    if not get(conversation_id, user_id):
        return []
    q = "SELECT role, content, metadata, timestamp FROM messages WHERE conversation_id = ? AND user_id = ? ORDER BY timestamp"
    with _conn() as conn:
        rows = conn.execute(q, (conversation_id, user_id)).fetchall()
    out = [{"role": r["role"], "content": r["content"],
            "metadata": json.loads(r["metadata"]) if r["metadata"] else None,
            "timestamp": r["timestamp"]} for r in rows]
    return out[-limit:] if limit else out


def message_count(conversation_id: str, user_id: str) -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND user_id = ?",
                            (conversation_id, user_id)).fetchone()[0]


def search(user_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search this user's conversation history (titles + message text). Isolation enforced."""
    like = f"%{query.strip()}%"
    with _conn() as conn:
        rows = conn.execute("""
            SELECT DISTINCT c.id, c.title, c.updated_at,
                   (SELECT content FROM messages m WHERE m.conversation_id = c.id AND m.user_id = c.user_id
                    AND m.content LIKE ? ORDER BY m.timestamp DESC LIMIT 1) AS snippet
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.user_id = ? AND (c.title LIKE ? OR m.content LIKE ?)
            ORDER BY c.updated_at DESC LIMIT ?
        """, (like, user_id, like, like, limit)).fetchall()
    return [dict(r) for r in rows]


init_db()
