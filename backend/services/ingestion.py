"""Ingestion orchestration: file -> parse -> chunk -> embed -> index -> register.

Ties together documents, embeddings, vectorstore and registry. Re-indexing a
document cleanly removes its old chunks first, so updates never leave orphans.
"""
import uuid
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.services import documents, registry, vectorstore
from backend.services.embeddings import embed_batch


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


def index_document(doc_id: str) -> int:
    """(Re)index a registered document. Returns the chunk count."""
    doc = registry.get_document(doc_id)
    if not doc:
        raise ValueError(f"Unknown document: {doc_id}")

    registry.set_index_status(doc_id, "indexing")
    # Remove any prior chunks for this document (idempotent re-index).
    vectorstore.delete_document(doc_id)

    try:
        segments = documents.parse_file(Path(doc["stored_path"]))
        chunks = documents.chunk_segments(
            segments, settings.chunk_size, settings.chunk_overlap
        )
        if not chunks:
            registry.set_index_status(doc_id, "empty", 0)
            return 0

        ids = [f"{doc_id}:{i}" for i in range(len(chunks))]
        texts = [c["text"] for c in chunks]
        metadatas = [_chunk_metadata(doc, c, i) for i, c in enumerate(chunks)]
        embeddings = embed_batch(texts)

        vectorstore.add_chunks(ids, embeddings, texts, metadatas)
        registry.set_index_status(doc_id, "indexed", len(chunks))
        return len(chunks)
    except Exception as exc:
        registry.set_index_status(doc_id, "error")
        raise exc


def register_and_index(filename: str, stored_path: Path, size_bytes: int,
                       metadata: dict[str, Any]) -> dict[str, Any]:
    """Create a registry entry for an already-saved file, then index it."""
    doc_id = uuid.uuid4().hex
    doc = {
        "id": doc_id,
        "filename": filename,
        "doc_type": Path(filename).suffix.lower().lstrip("."),
        "size_bytes": size_bytes,
        "chunk_count": 0,
        "index_status": "pending",
        "stored_path": str(stored_path),
    }
    for field in ("site", "department", "category", "version", "doc_date", "author", "status"):
        doc[field] = (metadata or {}).get(field)
    registry.add_document(doc)
    index_document(doc_id)
    return registry.get_document(doc_id)


def remove_document(doc_id: str) -> None:
    doc = registry.get_document(doc_id)
    vectorstore.delete_document(doc_id)
    registry.delete_document(doc_id)
    if doc and doc.get("stored_path"):
        try:
            Path(doc["stored_path"]).unlink(missing_ok=True)
        except OSError:
            pass
