from __future__ import annotations
from typing import List, Dict, Tuple, Callable, Optional, Iterable
from collections import defaultdict
import logging
import re

import numpy as np
from app.core.chroma_config import client
from app.retriever.embed import embedding_model

# Optional BM25 (fallback to TF-IDF-like scoring if missing)
HAVE_BM25 = False
try:
    from rank_bm25 import BM25Okapi  # type: ignore
    HAVE_BM25 = True
except Exception:
    pass

log = logging.getLogger(__name__)


# --------------------------- RRF core ---------------------------

def _rankify(ids: List[str]) -> List[Tuple[str, int]]:
    return [(d, i + 1) for i, d in enumerate(ids)]

def rrf(rankings: Dict[str, List[Tuple[str, int]]], k: int = 60) -> List[str]:
    """
    Reciprocal Rank Fusion.
    score(doc) = sum_over_lists( 1 / (k + rank(doc)) )
    Returns fused doc_id list sorted by score desc.
    """
    scores: Dict[str, float] = defaultdict(float)
    for name, pairs in rankings.items():
        for doc_id, rank in pairs:
            scores[doc_id] += 1.0 / (k + rank)
    # stable sort by (-score, doc_id)
    return [d for d, _ in sorted(scores.items(), key=lambda x: (-x[1], x[0]))]


# ------------------------ HYDE generation -----------------------

def default_hyde_prompts(query: str, n: int = 2) -> List[str]:
    """
    Fallback "HYDE-lite" prompts if you don't pass an LLM generator.
    Keeps it domain-friendly (policies, procedures, how-tos).
    """
    q = query.strip()
    variants = [
        q,
        f"Step-by-step instructions: {q}",
        f"Policy and procedure overview: {q}",
        f"Troubleshooting notes and prerequisites: {q}",
    ]
    # keep to top-n unique
    out, seen = [], set()
    for v in variants:
        if v.lower() not in seen:
            out.append(v)
            seen.add(v.lower())
        if len(out) >= n:
            break
    return out

def hyde_generate(
    query: str,
    n: int = 2,
    generator: Optional[Callable[[str], str]] = None,
) -> List[str]:
    """
    If `generator` is provided, it should be a callable that takes a prompt and returns text
    (e.g., a thin wrapper around your ask_llm_hf with low temperature + tiny max tokens).
    Otherwise, returns default HYDE-lite variants.
    """
    if generator is None:
        return default_hyde_prompts(query, n=n)

    prompts = []
    base = (
        "Write a concise factual answer (3–4 sentences) that might appear in an internal doc. "
        "No fluff. Topic: "
    )
    for i in range(n):
        try:
            txt = generator(base + query)
            txt = (txt or "").strip()
            if txt:
                prompts.append(txt)
        except Exception as e:
            log.warning("HYDE generator failed (var %s): %s", i + 1, e)

    if not prompts:
        return default_hyde_prompts(query, n=n)
    return prompts


# ------------------------- Chroma retrieval ---------------------
# ADD (above _get_collection)
class _ChromaEmbeddingWrapper:
    """Chroma expects a callable(list[str]) -> list[list[float]]."""
    def __call__(self, texts):
        # normalize for cosine; returns plain Python lists
        return embedding_model.encode(texts, normalize_embeddings=True).tolist()

def _get_collection(name: str):
    # Always include a callable wrapper, not the raw SentenceTransformer module
    return client.get_or_create_collection(
        name=name,
        embedding_function=_ChromaEmbeddingWrapper(),
    )


def retrieve_dense(collection_name: str, text: str, top_k: int = 8,
                   where: Optional[Dict] = None) -> Tuple[List[str], List[str], List[Dict]]:
    """
    Dense retrieval from Chroma by text. Returns (ids, documents, metadatas).
    """
    col = _get_collection(collection_name)
    res = col.query(query_texts=[text], n_results=top_k, where=where or {})
    ids = res.get("ids", [[]])[0] or []
    docs = res.get("documents", [[]])[0] or []
    metas = res.get("metadatas", [[]])[0] or []
    return ids, docs, metas

def retrieve_sparse_bm25(
    all_texts: List[str],
    query: str,
    top_k: int = 8
) -> List[int]:
    """
    Returns indices into all_texts sorted by BM25 score (desc).
    Provide the corpus once from your store if you want sparse fusion.
    """
    if not HAVE_BM25 or not all_texts:
        return []

    tokenized = [t.split() for t in all_texts]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(query.split())
    order = np.argsort(scores)[::-1][:top_k]
    return order.tolist()


# ----------------------- Build fused context --------------------

def build_context_from_collection(
    collection: str,
    query: str,
    *,
    k_each: int = 8,
    k_final: int = 6,
    rrf_k: int = 60,
    use_real_hyde: bool = True,
    hyde_n: int = 2,
    hyde_generator: Optional[Callable[[str], str]] = None,
    where: Optional[Dict] = None,
    include_sparse: bool = False,
    sparse_corpus_texts: Optional[List[str]] = None,
    sparse_corpus_ids: Optional[List[str]] = None,
) -> Tuple[str, List[Tuple[str, str, Dict]]]:
    """
    Returns:
      - context string (fused chunks joined with separators)
      - rows: list of (id, text, metadata) for UI citations

    Notes:
      - Set `include_sparse=True` only if you pass a corresponding corpus
        (aligned texts+ids) built at startup.
      - Pass `hyde_generator` if you want *real* HYDE via your LLM.
    """
    rankings: Dict[str, List[Tuple[str, int]]] = {}
    id2row: Dict[str, Tuple[str, str, Dict]] = {}  # id -> (id, text, meta)

    # Dense: original query
    ids, docs, metas = retrieve_dense(collection, query, k_each, where)
    rankings["dense_query"] = _rankify(ids)
    for i, d in enumerate(ids):
        id2row[d] = (d, docs[i], metas[i])

    # Dense: HYDE expansions
    if use_real_hyde and hyde_n > 0:
        hyde_texts = hyde_generate(query, n=hyde_n, generator=hyde_generator)
        for j, h in enumerate(hyde_texts):
            hid, hdocs, hmetas = retrieve_dense(collection, h, k_each, where)
            rankings[f"dense_hyde_{j}"] = _rankify(hid)
            for i, d in enumerate(hid):
                if d not in id2row:
                    id2row[d] = (d, hdocs[i], hmetas[i])

    # Sparse: BM25 (optional)
    if include_sparse and sparse_corpus_texts and sparse_corpus_ids:
        idxs = retrieve_sparse_bm25(sparse_corpus_texts, query, top_k=k_each)
        bm25_ids = [sparse_corpus_ids[i] for i in idxs]
        # Only include IDs that are also present in Chroma (optional)
        rankings["bm25"] = _rankify(bm25_ids)

    # Fuse with RRF
    fused_ids = rrf(rankings, k=rrf_k)

    # Take top-k_final, build context and rows
    chosen: List[Tuple[str, str, Dict]] = []
    pieces: List[str] = []
    for d in fused_ids:
        if len(chosen) >= k_final:
            break
        row = id2row.get(d)
        if not row:
            continue
        _id, _text, _meta = row
        if not (_text and _text.strip()):
            continue
        chosen.append(row)
        # compact separator with provenance for debugging
        src = _meta.get("source_file") or _meta.get("source") or _meta.get("title") or "source"
        page = _meta.get("page")
        header = f"[SOURCE: {src}{(' p'+str(page)) if page else ''}]"
        pieces.append(header + "\n" + _text.strip())

    context = "\n\n---\n\n".join(pieces)
    return context, chosen
