"""Ingestion orchestration: file -> parse -> chunk -> embed -> index -> register.

Ties together documents, embeddings, vectorstore and registry. Re-indexing a
document cleanly removes its old chunks first, so updates never leave orphans.
"""
import hashlib
import shutil
import uuid
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.services import documents, registry, vectorstore
from backend.services.embeddings import embed_batch
from backend.utils.security import (extension_of, is_allowed_extension,
                                    sanitize_filename)


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _chunk_metadata(doc: dict[str, Any], chunk: dict[str, Any], idx: int) -> dict[str, Any]:
    # Chroma metadata values must be str/int/float/bool (no None) -> drop empties.
    meta = {
        "doc_id": doc["id"],
        "filename": doc["filename"],
        "doc_type": doc["doc_type"],
        "chunk_index": idx,
    }
    if chunk.get("page"):
        meta["page"] = int(chunk["page"])
    if chunk.get("section"):
        meta["section"] = str(chunk["section"])
    for field in ("site", "department", "category", "version", "doc_date", "author", "status"):
        val = doc.get(field)
        if val:
            meta[field] = str(val)
    return meta


def index_document(doc_id: str, collection: str) -> int:
    """(Re)index a registered document into its property's collection. Returns chunk count."""
    doc = registry.get_document(doc_id)
    if not doc:
        raise ValueError(f"Unknown document: {doc_id}")

    registry.set_index_status(doc_id, "indexing")
    vectorstore.delete_document(collection, doc_id)  # idempotent re-index

    try:
        segments = documents.parse_file(Path(doc["stored_path"]))
        # Use semantic chunking if enabled (keeps related facts together)
        if settings.semantic_chunking:
            chunks = documents.semantic_chunk_segments(segments, settings.chunk_size)
        else:
            chunks = documents.chunk_segments(segments, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            registry.set_index_status(doc_id, "empty", 0)
            return 0

        ids = [f"{doc_id}:{i}" for i in range(len(chunks))]
        texts = [c["text"] for c in chunks]
        metadatas = [_chunk_metadata(doc, c, i) for i, c in enumerate(chunks)]
        embeddings = embed_batch(texts)

        vectorstore.add_chunks(collection, ids, embeddings, texts, metadatas)
        registry.set_index_status(doc_id, "indexed", len(chunks))
        return len(chunks)
    except Exception as exc:
        registry.set_index_status(doc_id, "error")
        raise exc


def register_and_index(filename: str, stored_path: Path, size_bytes: int,
                       metadata: dict[str, Any], content_hash: str | None,
                       property_id: int, collection: str) -> dict[str, Any]:
    """Create a registry entry for an already-saved file, then index it into a property."""
    doc_id = uuid.uuid4().hex
    doc = {
        "id": doc_id,
        "filename": filename,
        "doc_type": Path(filename).suffix.lower().lstrip("."),
        "size_bytes": size_bytes,
        "chunk_count": 0,
        "index_status": "pending",
        "stored_path": str(stored_path),
        "content_hash": content_hash,
        "property_id": property_id,
    }
    for field in ("site", "department", "category", "version", "doc_date", "author", "status"):
        doc[field] = (metadata or {}).get(field)
    registry.add_document(doc)
    index_document(doc_id, collection)
    return registry.get_document(doc_id)


def import_folder(property_id: int, collection: str,
                  folder: Path | None = None) -> dict[str, Any]:
    """Bulk-ingest every supported file in the import folder into one property."""
    folder = folder or settings.import_dir
    folder.mkdir(parents=True, exist_ok=True)
    added, skipped, errors = [], [], []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or not is_allowed_extension(path.name):
            continue
        try:
            data = path.read_bytes()
            digest = hash_bytes(data)
            if registry.find_by_hash(digest, property_id):
                skipped.append(path.name)
                continue
            stored = settings.upload_dir / f"{uuid.uuid4().hex}{extension_of(path.name)}"
            shutil.copy2(path, stored)
            register_and_index(sanitize_filename(path.name), stored, len(data), {}, digest,
                               property_id, collection)
            added.append(path.name)
        except Exception as exc:
            errors.append({"file": path.name, "error": str(exc)})
    return {"added": added, "skipped": skipped, "errors": errors, "import_dir": str(folder)}


def ingest_url(url: str, property_id: int, collection: str) -> dict[str, Any]:
    """Fetch a public web page and index its text into a property."""
    from backend.services import webfetch

    page = webfetch.fetch_url(url)  # raises ValueError on any problem
    body = f"Source URL: {page['url']}\nTitle: {page['title']}\n\n{page['text']}"
    digest = hash_bytes(body.encode("utf-8"))
    existing = registry.find_by_hash(digest, property_id)
    if existing:
        return {**existing, "duplicate": True}

    stored = settings.upload_dir / f"{uuid.uuid4().hex}.txt"
    stored.write_text(body, encoding="utf-8")
    filename = (page["title"] or url)[:180]
    if not filename.lower().endswith((".txt", ".md", ".html")):
        filename += " (web)"
    return register_and_index(filename, stored, len(body.encode("utf-8")),
                              {"author": page["url"]}, digest, property_id, collection)


def ingest_email_file(path: Path, property_id: int, collection: str) -> dict[str, Any]:
    """Parse an exported email file (.eml/.mbox/.pst) and index each message into a property."""
    from backend.services import email_ingest

    added, skipped, errors = 0, 0, []
    for msg in email_ingest.iter_messages(path):
        try:
            info = email_ingest.parse_message(msg)
            if not info["body"] and not info["attachments"]:
                continue
            text = email_ingest.build_document_text(info)
            digest = hash_bytes(text.encode("utf-8"))
            if registry.find_by_hash(digest, property_id):
                skipped += 1
                continue
            stored = settings.upload_dir / f"{uuid.uuid4().hex}.txt"
            stored.write_text(text, encoding="utf-8")
            filename = (info["subject"] or "email")[:150]
            metadata = {"category": "email", "author": (info["from"] or "")[:200],
                        "doc_date": info["date"]}
            register_and_index(filename, stored, len(text.encode("utf-8")), metadata, digest,
                               property_id, collection)
            added += 1
        except Exception as exc:
            errors.append(str(exc)[:200])
    return {"added": added, "skipped": skipped, "errors": errors[:20],
            "count": added + skipped}


def ingest_text(title: str, text: str, property_id: int, collection: str,
                source: str = "") -> dict[str, Any]:
    """Index pasted text (e.g. a copied Teams conversation or a quick note)."""
    title = (title or "Pasted note").strip()
    header = f"Title: {title}\n"
    if source:
        header += f"Source: {source}\n"
    body = header + "\n" + text.strip()
    digest = hash_bytes(body.encode("utf-8"))
    existing = registry.find_by_hash(digest, property_id)
    if existing:
        return {**existing, "duplicate": True}
    stored = settings.upload_dir / f"{uuid.uuid4().hex}.md"
    stored.write_text(body, encoding="utf-8")
    metadata = {"category": "teams" if "teams" in source.lower() else "note",
                "author": source[:200] or None}
    return register_and_index(title[:150], stored, len(body.encode("utf-8")), metadata, digest,
                              property_id, collection)


def remove_document(doc_id: str, collection: str) -> None:
    doc = registry.get_document(doc_id)
    vectorstore.delete_document(collection, doc_id)
    registry.delete_document(doc_id)
    if doc and doc.get("stored_path"):
        try:
            Path(doc["stored_path"]).unlink(missing_ok=True)
        except OSError:
            pass
