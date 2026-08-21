"""RAG retrieval pipeline.

    question -> embed -> metadata filter -> semantic search -> threshold ->
    dedup -> [optional rerank] -> ranked chunks -> context construction

All parameters (top_k, similarity threshold, context size) are configurable via
settings/.env. Optional reranking step improves answer quality by re-ordering chunks
by relevance.
"""
from typing import Any, Optional

from backend.config import settings
from backend.services import vectorstore
from backend.services.embeddings import embed_text
from backend.services import reranker


def retrieve(collection: str, question: str, filters: Optional[dict[str, Any]] = None,
             top_k: Optional[int] = None,
             threshold: Optional[float] = None) -> list[dict[str, Any]]:
    top_k = top_k or settings.top_k
    threshold = settings.similarity_threshold if threshold is None else threshold

    qvec = embed_text(question)
    hits = vectorstore.query(collection, qvec, top_k, _build_where(filters))

    # similarity threshold (primary filter)
    hits = [h for h in hits if h["similarity"] >= threshold]

    # Remove near-duplicates (keep order from initial retrieval)
    seen: set[str] = set()
    deduped = []
    for h in hits:
        key = h["text"][:120]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(h)

    # Optional: rerank chunks by relevance to put best match first
    if settings.use_reranker and deduped:
        deduped = reranker.rerank_chunks(question, deduped)

    return deduped


def build_context(hits: list[dict[str, Any]],
                  max_chars: Optional[int] = None) -> str:
    max_chars = max_chars or settings.max_context_chars
    parts, total = [], 0
    for idx, h in enumerate(hits, start=1):
        m = h["metadata"]
        loc = ""
        if m.get("page"):
            loc += f" p.{m['page']}"
        if m.get("section"):
            loc += f" — {m['section']}"
        block = f"[{idx}] {m.get('filename', 'unknown')}{loc}\n{h['text']}"
        if total + len(block) > max_chars and parts:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)


def _build_where(filters: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Translate a flat {field: value} filter into a Chroma `where` clause."""
    if not filters:
        return None
    conds = [{k: {"$eq": v}} for k, v in filters.items()
             if v not in (None, "", "all")]
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}
