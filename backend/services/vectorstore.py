"""Local ChromaDB vector store — one collection per property (isolated knowledge bases).

Persistent, embedded, no server, telemetry disabled. Callers pass the property's collection name so
each property's data is fully isolated.
"""
from functools import lru_cache
from typing import Any, Optional


@lru_cache(maxsize=1)
def _client():
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    from backend.config import settings
    return chromadb.PersistentClient(
        path=str(settings.chroma_dir),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
    )


_collections: dict[str, Any] = {}


def _collection(name: str):
    if name not in _collections:
        _collections[name] = _client().get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"})
    return _collections[name]


def add_chunks(collection: str, ids: list[str], embeddings: list[list[float]],
               documents: list[str], metadatas: list[dict[str, Any]]) -> None:
    if not ids:
        return
    _collection(collection).add(ids=ids, embeddings=embeddings,
                                documents=documents, metadatas=metadatas)


def query(collection: str, embedding: list[float], top_k: int,
          where: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    res = _collection(collection).query(
        query_embeddings=[embedding], n_results=top_k, where=where or None,
        include=["documents", "metadatas", "distances"])
    if not res["ids"] or not res["ids"][0]:
        return []
    out = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({"text": doc, "metadata": meta or {}, "similarity": max(0.0, 1.0 - float(dist))})
    return out


def delete_document(collection: str, doc_id: str) -> None:
    _collection(collection).delete(where={"doc_id": doc_id})


def count(collection: str) -> int:
    try:
        return _collection(collection).count()
    except Exception:
        return 0


def drop_collection(collection: str) -> None:
    try:
        _client().delete_collection(collection)
    except Exception:
        pass
    _collections.pop(collection, None)
