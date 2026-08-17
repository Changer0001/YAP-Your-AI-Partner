"""Properties (tenants). Each property is an isolated knowledge base.

Isolation is by **separate vector collection** per property (a "different database" for each site) plus
a `property_id` column on documents/users. The first/default property keeps the legacy collection
name so existing data is preserved.
"""
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException

from backend.config import settings
from backend.services import auth

LEGACY_COLLECTION = "it_knowledge"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.registry_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                collection TEXT UNIQUE NOT NULL,
                created_at TEXT
            )
            """
        )


def _row(r) -> dict[str, Any]:
    return {"id": r["id"], "name": r["name"], "collection": r["collection"], "created_at": r["created_at"]}


def list_properties() -> list[dict[str, Any]]:
    with _conn() as conn:
        return [_row(r) for r in conn.execute("SELECT * FROM properties ORDER BY id").fetchall()]


def get_property(pid: int) -> Optional[dict[str, Any]]:
    with _conn() as conn:
        r = conn.execute("SELECT * FROM properties WHERE id = ?", (pid,)).fetchone()
    return _row(r) if r else None


def count() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]


def create_property(name: str, collection: Optional[str] = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _conn() as conn:
        cur = conn.execute("INSERT INTO properties (name, collection, created_at) VALUES (?, ?, ?)",
                           (name.strip(), collection or "__pending__", now))
        pid = cur.lastrowid
        coll = collection or f"kb_{pid}"
        conn.execute("UPDATE properties SET collection = ? WHERE id = ?", (coll, pid))
    return get_property(pid)


def rename_property(pid: int, name: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE properties SET name = ? WHERE id = ?", (name.strip(), pid))


def delete_property(pid: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM properties WHERE id = ?", (pid,))


def ensure_default() -> dict[str, Any]:
    """Guarantee at least one property exists; the first keeps the legacy collection."""
    props = list_properties()
    if props:
        return props[0]
    return create_property("Default", collection=LEGACY_COLLECTION)


def current_property(user: dict = Depends(auth.require_auth),
                     x_property_id: str = Header(default="")) -> dict[str, Any]:
    """Resolve the property a request operates on.

    - superadmin: the property named in X-Property-Id (else the first). Full visibility.
    - admin/user: their assigned property; they cannot override it.
    """
    if user["role"] == "superadmin":
        if x_property_id and x_property_id.isdigit():
            p = get_property(int(x_property_id))
            if p:
                return p
        props = list_properties()
        if not props:
            raise HTTPException(400, "No properties exist yet")
        return props[0]
    pid = user.get("property_id")
    if not pid:
        raise HTTPException(403, "No property is assigned to your account. Ask an administrator.")
    p = get_property(pid)
    if not p:
        raise HTTPException(403, "Your assigned property no longer exists.")
    return p
