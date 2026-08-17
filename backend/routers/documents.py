"""Document management endpoints: upload, list, view, edit metadata, re-index, delete."""
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.config import settings
from backend.services import ingestion, registry
from backend.utils.security import (extension_of, is_allowed_extension,
                                    sanitize_filename)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def list_documents():
    return registry.list_documents()


@router.get("/{doc_id}")
def get_document(doc_id: str):
    doc = registry.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    site: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    doc_date: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
):
    filename = sanitize_filename(file.filename or "")
    if not is_allowed_extension(filename):
        raise HTTPException(400, f"Unsupported file type. Allowed: PDF, DOCX, XLSX, TXT, MD, CSV")

    data = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(413, f"File too large (limit {settings.max_upload_mb} MB)")
    if not data:
        raise HTTPException(400, "Empty file")

    # Store under a generated name (no user-controlled path -> no traversal).
    stored_path = settings.upload_dir / f"{uuid.uuid4().hex}{extension_of(filename)}"
    stored_path.write_bytes(data)

    metadata = {"site": site, "department": department, "category": category,
                "version": version, "doc_date": doc_date, "author": author,
                "status": status}
    try:
        doc = ingestion.register_and_index(filename, stored_path, len(data), metadata)
    except Exception as exc:
        raise HTTPException(500, f"Indexing failed: {exc}")
    return doc


@router.patch("/{doc_id}")
def update_metadata(doc_id: str, updates: dict):
    doc = registry.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    allowed = {"site", "department", "category", "version", "doc_date", "author", "status"}
    registry.update_document(doc_id, {k: v for k, v in updates.items() if k in allowed})
    # Propagate new metadata into the chunks so filtering stays correct.
    try:
        ingestion.index_document(doc_id)
    except Exception as exc:
        raise HTTPException(500, f"Re-index after metadata update failed: {exc}")
    return registry.get_document(doc_id)


@router.post("/{doc_id}/reindex")
def reindex(doc_id: str):
    if not registry.get_document(doc_id):
        raise HTTPException(404, "Document not found")
    try:
        count = ingestion.index_document(doc_id)
    except Exception as exc:
        raise HTTPException(500, f"Re-index failed: {exc}")
    return {"doc_id": doc_id, "chunk_count": count, "status": "indexed"}


@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    if not registry.get_document(doc_id):
        raise HTTPException(404, "Document not found")
    ingestion.remove_document(doc_id)
    return {"deleted": doc_id}
