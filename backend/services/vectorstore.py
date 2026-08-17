"""Local ChromaDB vector store wrapper.

Persistent, embedded, no server. Telemetry disabled (privacy). We supply our
own embeddings (computed locally via Ollama), so Chroma is used purely as a
similarity index with metadata filtering.
"""
from functools import lru_cache
from typing import Any, Optional

from backend.config import settings

COLLECTION_NAME = "it_knowledge"


@lru_cache(maxsize=1)
def _collection():
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    client = chromadb.PersistentClient(
        path=str(settings.chroma_dir),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
    )
    # cosine space so similarity = 1 - distance
    return client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def add_chunks(ids: list[str], embeddings: list[list[float]],
               documents: list[str], metadatas: list[dict[str, Any]]) -> None:
    if not ids:
        return
    _collection().add(ids=ids, embeddings=embeddings,
                      documents=documents, metadatas=metadatas)


def query(embedding: list[float], top_k: int,
          where: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    res = _collection().query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=where or None,
        include=["documents", "metadatas", "distances"],
    )
    if not res["ids"] or not res["ids"][0]:
        return []
    out = []
    for doc, meta, dist in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        out.append({"text": doc, "metadata": meta or {},
                    "similarity": max(0.0, 1.0 - float(dist))})
    return out


def delete_document(doc_id: str) -> None:
    _collection().delete(where={"doc_id": doc_id})


def count() -> int:
    return _collection().count()


def distinct_values(field: str) -> list[str]:
    res = _collection().get(include=["metadatas"])
    vals = {m.get(field) for m in (res["metadatas"] or []) if m and m.get(field)}
    return sorted(v for v in vals if v)
