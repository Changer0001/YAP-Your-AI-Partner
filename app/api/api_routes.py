# app/api/api_routes.py
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
import logging
from sqlalchemy.orm import Session
import json
import re

from app.db.database import get_db
from app.api.auth import verify_token, register_user, authenticate_user
from app.core.utils import get_user_id
from app.db.chat_store import save_chat_history, get_user_history, get_recent_history
from app.llm.llm_interface import ask_llm_hf, ask_llm_hf_stream, format_history_blocks
from app.retriever.rrf_hyde import build_context_from_collection

# Routers
from app.api.servicenow_router import router as servicenow_router
from app.api.teams_webhook import router as router_teams

router = APIRouter()
router.include_router(servicenow_router)
router.include_router(router_teams)
logging.basicConfig(level=logging.INFO)

# ---------- Small-talk detector ----------
_GREETING_RX  = re.compile(r"\b(hi|hey|hello|good (morning|afternoon|evening))\b", re.I)
_THANKS_RX    = re.compile(r"\b(thanks|thank you|appreciate(d)?|much appreciated)\b", re.I)
_GOODBYE_RX   = re.compile(r"\b(bye|good night|see you|take care)\b", re.I)
_HOWAREYOU_RX = re.compile(r"\b(how (are|r) (you|u)|how’s it going|how are things)\b", re.I)

def _is_smalltalk_text(text: str) -> bool:
    t = (text or "").strip()
    return bool(
        _GREETING_RX.search(t)
        or _THANKS_RX.search(t)
        or _GOODBYE_RX.search(t)
        or _HOWAREYOU_RX.search(t)
    )

# ---------- Simple lexical relevance gate for RAG ----------
_STOP = set(
    "a an the and or but if while to for of on in at from by with as into over under between "
    "this that those these is are was were be been being do does did so such it its we our you your they their".split()
)

def _tok(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9']+", (s or "").lower()) if w not in _STOP and len(w) > 2}

def _ctx_relevance(question: str, rows) -> float:
    """
    Quick lexical relevance between the question and the top retrieved text chunks.
    rows is expected to be a list of tuples: (rid, text, meta)
    """
    q = _tok(question)
    if not q:
        return 0.0
    top_text = " ".join((text or "") for (_, text, _) in (rows[:3] if rows else []))
    c = _tok(top_text)
    if not c:
        return 0.0
    # coverage of question terms by context
    return len(q & c) / len(q)

# ── Models ─────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class HistoryEntry(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    question: str
    collection: str = "example_business_docs"
    use_hyde: bool = True
    k_final: int = 6
    history: List[HistoryEntry] = Field(default_factory=list)  # avoid mutable default

# ── Helpers ───────────────────────────────────────────────────────────
def _normalize_history(h):
    out = []
    for m in h or []:
        if hasattr(m, "model_dump"):
            out.append(m.model_dump())
        elif isinstance(m, dict):
            out.append(m)
        else:
            try:
                out.append(dict(m))
            except Exception:
                pass
    return out

# ── Auth ─────────────────────────────────────────────────────────────
@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if not register_user(req.username, req.password, db):
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"message": "User registered successfully"}

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    token = authenticate_user(req.username, req.password, db)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": token}

# ── /ask (Blocking) ────────────────────────────────────────────────────
@router.post("/ask")
def ask(req: AskRequest, username=Depends(verify_token)):
    """
    Blocking Q&A with RRF + HYDE retrieval.
    Returns final answer + source list for UI citations.
    Enforces RAG-only answers for non-small-talk queries.
    """
    try:
        user_id = get_user_id(username)

        # History (optional for small-talk)
        history = req.history or get_recent_history(user_id)
        history_dicts = _normalize_history(history)
        history_blocks = format_history_blocks(history_dicts)

        # 1) Small-talk fast path (no retrieval / model required)
        if _is_smalltalk_text(req.question):
            answer = "I’m doing well! How can I help with IT today?"
            save_chat_history(user_id, req.question, answer)
            return {"question": req.question, "answer": answer, "sources": []}

        # 2) Retrieve with RRF + HYDE
        ctx, rows = build_context_from_collection(
            collection=req.collection,
            query=req.question,
            use_real_hyde=req.use_hyde,
            k_final=req.k_final,
        )
        logging.info(f"[retrieval:/ask] ctx_chars={len(ctx)} rows={len(rows)} q='{req.question[:60]}'")

        # 3) Strict RAG gate for non-small-talk
        relevance = _ctx_relevance(req.question, rows)
        if (not rows) or (not ctx.strip()) or (relevance < 0.15):
            answer = "I don’t know."
            save_chat_history(user_id, req.question, answer)
            return {"question": req.question, "answer": answer, "sources": []}

        # 4) Ask the LLM (guarded)
        try:
            answer = ask_llm_hf(
                question=req.question,
                history_blocks=history_blocks,
                doc_context=ctx,
                user_id=user_id,
            )
        except Exception:
            answer = "I don’t know."

        # 5) Save + sources
        save_chat_history(user_id, req.question, answer)
        sources = [
            {
                "id": rid,
                "title": (meta.get("title") or meta.get("source_file") or (text[:80] + "…")),
                "url": meta.get("url", ""),
                "page": meta.get("page"),
            }
            for (rid, text, meta) in rows
        ]
        return {"question": req.question, "answer": answer, "sources": sources}

    except HTTPException:
        raise
    except Exception:
        # Never bubble errors to UI/clients
        return {"question": req.question, "answer": "I don’t know.", "sources": []}

# ── /ask/stream ───────────────────────────────────────────────────────
@router.post("/ask/stream")
async def stream(req: AskRequest, username=Depends(verify_token)):
    """
    Server-Sent Events stream of answer tokens.
    Always emits a response (no SSE error events) so UIs never show [ERROR].
    """
    try:
        user_id = get_user_id(username)

        # History
        history = req.history or get_recent_history(user_id)
        history_dicts = _normalize_history(history)
        history_blocks = format_history_blocks(history_dicts)

        # --- Small-talk: immediate canned stream ---
        if _is_smalltalk_text(req.question):
            def sse_small():
                yield "retry: 2000\n\n"
                yield "event: sources\ndata: []\n\n"
                yield 'data: {"choices":[{"delta":{"content":"I’m doing well! How can I help with IT today?"}}]}\n\n'
                yield "event: done\ndata: {}\n\n"
            return StreamingResponse(sse_small(), media_type="text/event-stream")

        # Retrieval
        ctx, rows = build_context_from_collection(
            collection=req.collection,
            query=req.question,
            use_real_hyde=req.use_hyde,
            k_final=req.k_final,
        )
        logging.info(f"[retrieval:/ask_stream] ctx_chars={len(ctx)} rows={len(rows)} q='{req.question[:60]}'")

        # Sources for the UI (may be empty)
        sources = [
            {
                "id": rid,
                "title": (meta.get("title") or meta.get("source_file") or (text[:80] + "…")),
                "url": meta.get("url", ""),
                "page": meta.get("page"),
            }
            for (rid, text, meta) in rows
        ]

        # RAG gate → stream a graceful decline (no error)
        relevance = _ctx_relevance(req.question, rows)
        if (not rows) or (not ctx.strip()) or (relevance < 0.15):
            def sse_decline():
                yield "retry: 2000\n\n"
                yield "event: sources\ndata: []\n\n"
                yield 'data: {"choices":[{"delta":{"content":"I don’t know."}}]}\n\n'
                yield "event: done\ndata: {}\n\n"
            try:
                save_chat_history(user_id, req.question, "I don’t know.")
            except Exception:
                pass
            return StreamingResponse(sse_decline(), media_type="text/event-stream")

        # Stream from LLM; on error, stream fallback tokens instead of error event
        def sse_generator():
            full_answer = ""
            try:
                yield "retry: 2000\n\n"
                yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
                for token in ask_llm_hf_stream(
                    question=req.question,
                    history_blocks=history_blocks,
                    doc_context=[ctx],
                    user_id=user_id,
                ):
                    if not token:
                        continue
                    full_answer += token
                    yield f'data: {json.dumps({"choices":[{"delta":{"content": token}}]})}\n\n'
                yield "event: done\ndata: {}\n\n"
            except Exception:
                # No "error" events → UIs never show [ERROR]
                yield 'data: {"choices":[{"delta":{"content":"I don’t know."}}]}\n\n'
                yield "event: done\ndata: {}\n\n"
            finally:
                try:
                    save_chat_history(user_id, req.question, full_answer or "I don’t know.")
                except Exception:
                    pass

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    except HTTPException:
        raise
    except Exception:
        # Final safety fallback
        def sse_fail():
            yield "retry: 2000\n\n"
            yield "event: sources\ndata: []\n\n"
            yield 'data: {"choices":[{"delta":{"content":"I don’t know."}}]}\n\n'
            yield "event: done\ndata: {}\n\n"
        return StreamingResponse(sse_fail(), media_type="text/event-stream")

# ── /history ──────────────────────────────────────────────────────────
@router.get("/history")
def history(username=Depends(verify_token)):
    user_id = get_user_id(username)
    return get_user_history(user_id)
