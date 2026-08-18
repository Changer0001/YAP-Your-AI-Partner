"""Document management — scoped to the caller's property (tenant)."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.config import settings
from backend.services import ingestion, registry
from backend.services.properties import current_property
from backend.utils.security import (extension_of, is_allowed_extension, sanitize_filename)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _owned(doc_id: str, prop: dict) -> dict:
    doc = registry.get_document(doc_id)
    if not doc or doc.get("property_id") != prop["id"]:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("")
def list_documents(prop: dict = Depends(current_property)):
    return registry.list_documents(prop["id"])


@router.get("/{doc_id}")
def get_document(doc_id: str, prop: dict = Depends(current_property)):
    return _owned(doc_id, prop)


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    site: Optional[str] = Form(None), department: Optional[str] = Form(None),
    category: Optional[str] = Form(None), version: Optional[str] = Form(None),
    doc_date: Optional[str] = Form(None), author: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    prop: dict = Depends(current_property),
):
    filename = sanitize_filename(file.filename or "")
    if not is_allowed_extension(filename):
        raise HTTPException(400, "Unsupported file type. Allowed: PDF, DOCX, XLSX, TXT, MD, CSV")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File too large (limit {settings.max_upload_mb} MB)")
    if not data:
        raise HTTPException(400, "Empty file")

    digest = ingestion.hash_bytes(data)
    existing = registry.find_by_hash(digest, prop["id"])
    if existing:
        return {**existing, "duplicate": True}

    stored_path = settings.upload_dir / f"{uuid.uuid4().hex}{extension_of(filename)}"
    stored_path.write_bytes(data)
    metadata = {"site": site, "department": department, "category": category, "version": version,
                "doc_date": doc_date, "author": author, "status": status}
    try:
        return ingestion.register_and_index(filename, stored_path, len(data), metadata, digest,
                                            prop["id"], prop["collection"])
    except Exception as exc:
        raise HTTPException(500, f"Indexing failed: {exc}")


@router.post("/import")
def import_from_folder(prop: dict = Depends(current_property)):
    return ingestion.import_folder(prop["id"], prop["collection"])


class UrlBody(BaseModel):
    url: str


@router.post("/url")
def ingest_url(body: UrlBody, prop: dict = Depends(current_property)):
    try:
        return ingestion.ingest_url(body.url, prop["id"], prop["collection"])
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Failed to ingest URL: {exc}")


@router.post("/email")
async def ingest_email(file: UploadFile = File(...), prop: dict = Depends(current_property)):
    from backend.services.email_ingest import EMAIL_EXTENSIONS

    filename = sanitize_filename(file.filename or "")
    if extension_of(filename) not in EMAIL_EXTENSIONS:
        raise HTTPException(400, "Unsupported email file. Allowed: .eml, .mbox, .pst")

    # Stream to a temp file so large PST/mbox files don't load into memory.
    tmp = settings.upload_dir / f"email_{uuid.uuid4().hex}{extension_of(filename)}"
    max_bytes = settings.email_max_upload_mb * 1024 * 1024
    size = 0
    try:
        with open(tmp, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"File too large (limit {settings.email_max_upload_mb} MB)")
                out.write(chunk)
        try:
            return ingestion.ingest_email_file(tmp, prop["id"], prop["collection"])
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    finally:
        tmp.unlink(missing_ok=True)  # the per-email .txt docs are kept; the source file isn't


@router.patch("/{doc_id}")
def update_metadata(doc_id: str, updates: dict, prop: dict = Depends(current_property)):
    _owned(doc_id, prop)
    allowed = {"site", "department", "category", "version", "doc_date", "author", "status"}
    registry.update_document(doc_id, {k: v for k, v in updates.items() if k in allowed})
    try:
        ingestion.index_document(doc_id, prop["collection"])
    except Exception as exc:
        raise HTTPException(500, f"Re-index failed: {exc}")
    return registry.get_document(doc_id)


@router.post("/{doc_id}/reindex")
def reindex(doc_id: str, prop: dict = Depends(current_property)):
    _owned(doc_id, prop)
    try:
        count = ingestion.index_document(doc_id, prop["collection"])
    except Exception as exc:
        raise HTTPException(500, f"Re-index failed: {exc}")
    return {"doc_id": doc_id, "chunk_count": count, "status": "indexed"}


@router.delete("/{doc_id}")
def delete_document(doc_id: str, prop: dict = Depends(current_property)):
    _owned(doc_id, prop)
    ingestion.remove_document(doc_id, prop["collection"])
    return {"deleted": doc_id}
