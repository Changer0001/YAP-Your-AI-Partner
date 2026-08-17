"""Direct knowledge-base search (no LLM) — inspect what the index contains (per property)."""
from fastapi import APIRouter, Depends, HTTPException

from backend.models import SearchRequest
from backend.services import rag
from backend.services.properties import current_property

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search")
def search(req: SearchRequest, prop: dict = Depends(current_property)):
    query = (req.query or "").strip()
    if not query:
        raise HTTPException(400, "Query is required")
    try:
        hits = rag.retrieve(prop["collection"], query, req.filters, top_k=req.top_k, threshold=0.0)
    except Exception as exc:
        raise HTTPException(503, f"Search failed: {exc}. Is Ollama running?")
    results = []
    for h in hits:
        m = h["metadata"]
        results.append({
            "filename": m.get("filename"),
            "page": m.get("page"),
            "section": m.get("section"),
            "site": m.get("site"),
            "doc_type": m.get("doc_type"),
            "similarity": round(h["similarity"], 3),
            "excerpt": h["text"][:400],
        })
    return {"query": query, "count": len(results), "results": results}
