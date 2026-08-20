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


def allowed_property_ids(user: dict) -> Optional[set[int]]:
    """The set of property ids a user may access, or None for superadmin (all)."""
    if user["role"] == "superadmin":
        return None
    ids = set(user.get("property_ids") or ([] if user.get("property_id") is None else [user["property_id"]]))
    return ids


def current_property(user: dict = Depends(auth.require_auth),
                     x_property_id: str = Header(default="")) -> dict[str, Any]:
    """Resolve the property a request operates on, validated against what the user may access.

    - superadmin: any property (X-Property-Id, else the first).
    - admin/user: only among their assigned properties; the header is honored only if allowed.
    """
    allowed = allowed_property_ids(user)
    if allowed is not None and not allowed:
        raise HTTPException(403, "No property is assigned to your account. Ask an administrator.")

    # honor an explicit selection if the user is allowed to use it
    if x_property_id and x_property_id.isdigit():
        pid = int(x_property_id)
        if allowed is None or pid in allowed:
            p = get_property(pid)
            if p:
                return p

    # default: first available/allowed property
    candidates = list_properties() if allowed is None else [get_property(i) for i in sorted(allowed)]
    for p in candidates:
        if p:
            return p
    raise HTTPException(400 if allowed is None else 403,
                        "No properties exist yet" if allowed is None else "Your assigned property no longer exists.")
