"""Reranking module — re-scores retrieved chunks by relevance using a specialized model.

This improves answer quality by putting the best-matching chunk first, so the LLM reads
the most relevant information. Often outperforms upgrading to a larger model.

Optional: set USE_RERANKER=true to enable. Requires bge-reranker-v2-m3 pulled in Ollama.
"""
from typing import Any, Optional

from backend.config import settings


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def rerank_chunks(query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Re-rank retrieved chunks by relevance using bge-reranker.

    Returns chunks sorted by relevance score (highest first).
    Falls back to original order if reranking fails or is disabled.
    """
    if not settings.use_reranker or not chunks:
        return chunks

    try:
        from ollama import Client
        client = Client(host=settings.ollama_host)

        # Prepare texts for reranking
        chunk_texts = [c["text"] for c in chunks]

        # Call reranker embeddings for query and all chunks
        query_resp = client.embeddings(model=settings.reranker_model, prompt=query)
        query_emb = query_resp.get("embedding", [])

        if not query_emb:
            return chunks

        # Score each chunk
        scores = []
        for chunk_text in chunk_texts:
            chunk_resp = client.embeddings(model=settings.reranker_model, prompt=chunk_text)
            chunk_emb = chunk_resp.get("embedding", [])
            if chunk_emb:
                score = cosine_similarity(query_emb, chunk_emb)
                scores.append(score)
            else:
                scores.append(0.0)

        # Sort chunks by score (descending)
        ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
        return [chunk for chunk, _ in ranked]

    except Exception as e:
        # Reranking failed; return original order (don't break retrieval)
        import logging
        logging.warning(f"Reranking failed (non-fatal): {e}")
        return chunks
