"""SQLite document registry.

Tracks every document's identity, metadata, indexing status and chunk count so
the Documents UI can list / edit / delete / re-index. Local file, no server.
"""
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from backend.config import settings

_FIELDS = [
    "id", "filename", "doc_type", "size_bytes", "chunk_count", "index_status",
    "site", "department", "category", "version", "doc_date", "author", "status",
    "created_at", "updated_at", "stored_path", "content_hash",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.registry_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                doc_type TEXT,
                size_bytes INTEGER,
                chunk_count INTEGER DEFAULT 0,
                index_status TEXT DEFAULT 'pending',
                site TEXT, department TEXT, category TEXT, version TEXT,
                doc_date TEXT, author TEXT, status TEXT,
                created_at TEXT, updated_at TEXT, stored_path TEXT,
                content_hash TEXT
            )
            """
        )
        # Migration for databases created before content_hash existed.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
        if "content_hash" not in cols:
            conn.execute("ALTER TABLE documents ADD COLUMN content_hash TEXT")


def add_document(doc: dict[str, Any]) -> None:
    doc.setdefault("created_at", _now())
    doc["updated_at"] = _now()
    cols = ", ".join(_FIELDS)
    placeholders = ", ".join(f":{f}" for f in _FIELDS)
    row = {f: doc.get(f) for f in _FIELDS}
    with _conn() as conn:
        conn.execute(f"INSERT INTO documents ({cols}) VALUES ({placeholders})", row)


def update_document(doc_id: str, updates: dict[str, Any]) -> None:
    updates = {k: v for k, v in updates.items() if k in _FIELDS and k != "id"}
    if not updates:
        return
    updates["updated_at"] = _now()
    sets = ", ".join(f"{k} = :{k}" for k in updates)
    updates["_id"] = doc_id
    with _conn() as conn:
        conn.execute(f"UPDATE documents SET {sets} WHERE id = :_id", updates)


def set_index_status(doc_id: str, status: str, chunk_count: Optional[int] = None) -> None:
    updates: dict[str, Any] = {"index_status": status}
    if chunk_count is not None:
        updates["chunk_count"] = chunk_count
    update_document(doc_id, updates)


def get_document(doc_id: str) -> Optional[dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return dict(row) if row else None


def list_documents() -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_document(doc_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


def find_by_hash(content_hash: str) -> Optional[dict[str, Any]]:
    if not content_hash:
        return None
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE content_hash = ?", (content_hash,)
        ).fetchone()
    return dict(row) if row else None


def stats() -> dict[str, Any]:
    with _conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = conn.execute(
            "SELECT COALESCE(SUM(chunk_count), 0) FROM documents"
        ).fetchone()[0]
        sites = conn.execute(
            "SELECT COUNT(DISTINCT site) FROM documents WHERE site IS NOT NULL AND site != ''"
        ).fetchone()[0]
    return {"documents": total, "chunks": chunks, "properties": sites}


# Ensure the schema exists as soon as the registry is imported (idempotent),
# so endpoints never hit a missing table if the app's startup hook hasn't run.
init_db()
