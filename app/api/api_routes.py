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
# in app/api/api_routes.py
from app.api.servicenow_routes import router_sn
from app.api.teams_webhook import router_teams



router = APIRouter()
router.include_router(router_sn)
router.include_router(router_teams)
logging.basicConfig(level=logging.INFO)

# ---------- Lightweight lexical small-talk detector (to bypass RAG gate) ----------
_GREETING_RX  = re.compile(r"\b(hi|hey|hello|good (morning|afternoon|evening))\b", re.I)
_THANKS_RX    = re.compile(r"\b(thanks|thank you|appreciate(d)?|much appreciated)\b", re.I)
_GOODBYE_RX   = re.compile(r"\b(bye|good night|see you|take care)\b", re.I)
_HOWAREYOU_RX = re.compile(r"\b(how (are|r) (you|u)|how’s it going|how are things)\b", re.I)

def _is_smalltalk_text(text: str) -> bool:
    t = (text or "").strip()
    return bool(
        _GREETING_RX.search(t) or _THANKS_RX.search(t) or _GOODBYE_RX.search(t) or _HOWAREYOU_RX.search(t)
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

        # 1) Prefer provided history, else recent; normalize to dicts
        history = req.history or get_recent_history(user_id)
        history_dicts = _normalize_history(history)

        # 2) Retrieve with RRF + HYDE
        ctx, rows = build_context_from_collection(
            collection=req.collection,
            query=req.question,
            use_real_hyde=req.use_hyde,
            k_final=req.k_final,
        )
        logging.info(f"[retrieval:/ask] ctx_chars={len(ctx)} rows={len(rows)} q='{req.question[:60]}'")

        # 3) Strict RAG gate for non-small-talk: require non-empty & relevant context
        if not _is_smalltalk_text(req.question):
            relevance = _ctx_relevance(req.question, rows)
            if (not rows) or (not ctx.strip()) or (relevance < 0.15):
                answer = "I don’t know."
                save_chat_history(user_id, req.question, answer)
                return {"question": req.question, "answer": answer, "sources": []}

        # 4) Convert history for LLM and pass fused context
        history_blocks = format_history_blocks(history_dicts)
        doc_context_str = ctx

        # 5) Ask the LLM grounded on the built context
        answer = ask_llm_hf(
            question=req.question,
            history_blocks=history_blocks,
            doc_context=doc_context_str,  # pass fused context string
            user_id=user_id,
        )

        # 6) Save chat
        save_chat_history(user_id, req.question, answer)

        # 7) Build sources for UI (rows = [(id, text, meta), ...])
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
    except Exception as e:
        logging.exception("❌ /ask failed:")
        raise HTTPException(status_code=500, detail=str(e))

# ── /ask/stream ───────────────────────────────────────────────────────
@router.post("/ask/stream")
async def stream(req: AskRequest, username=Depends(verify_token)):
    """
    Server-Sent Events stream of answer tokens.
    Sends an initial 'sources' event with citations before streaming tokens.
    Enforces RAG-only answers for non-small-talk queries.
    """
    try:
        user_id = get_user_id(username)

        # 1) Prefer provided history, else recent; normalize to dicts
        history = req.history or get_recent_history(user_id)
        history_dicts = _normalize_history(history)

        # 2) Retrieve with RRF + HYDE
        ctx, rows = build_context_from_collection(
            collection=req.collection,
            query=req.question,
            use_real_hyde=req.use_hyde,
            k_final=req.k_final,
        )
        logging.info(f"[retrieval:/ask_stream] ctx_chars={len(ctx)} rows={len(rows)} q='{req.question[:60]}'")

        # 3) Non-small-talk strict gate: if no usable context, stream a short decline and end
        if not _is_smalltalk_text(req.question):
            relevance = _ctx_relevance(req.question, rows)
            if (not rows) or (not ctx.strip()) or (relevance < 0.15):
                def sse_generator_empty():
                    yield "retry: 2000\n\n"
                    yield f"event: sources\ndata: {json.dumps([])}\n\n"
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': 'I don’t know.'}}]})}\n\n"
                    yield "event: done\ndata: {}\n\n"
                    try:
                        save_chat_history(user_id, req.question, "I don’t know.")
                    except Exception:
                        logging.exception("⚠️ Failed to save chat history (empty).")
                return StreamingResponse(sse_generator_empty(), media_type="text/event-stream")

        # 4) Convert messages to LLM format
        history_blocks = format_history_blocks(history_dicts)
        doc_context = [ctx]  # ask_llm_hf_stream expects a list[str]

        # 5) Prepare sources for UI (rows = [(id, text, meta), ...])
        sources = [
            {
                "id": rid,
                "title": (meta.get("title") or meta.get("source_file") or (text[:80] + "…")),
                "url": meta.get("url", ""),
                "page": meta.get("page"),
            }
            for (rid, text, meta) in rows
        ]

        def sse_generator():
            full_answer = ""
            try:
                # (Optional) client retry hint
                yield "retry: 2000\n\n"

                # Send sources first
                yield f"event: sources\ndata: {json.dumps(sources)}\n\n"

                # Stream tokens from the model
                for token in ask_llm_hf_stream(
                    question=req.question,
                    history_blocks=history_blocks,
                    doc_context=doc_context,
                    user_id=user_id,
                ):
                    if not token:
                        continue
                    full_answer += token
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': token}}]})}\n\n"

                yield "event: done\ndata: {}\n\n"

            except Exception as e:
                logging.exception("❌ Stream error:")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            finally:
                # Persist the complete answer
                try:
                    save_chat_history(user_id, req.question, full_answer)
                except Exception:
                    logging.exception("⚠️ Failed to save chat history at stream end.")

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ /ask/stream failed:")
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': str(e)})}\n\n"]),
            media_type="text/event-stream",
        )

# ── /history ──────────────────────────────────────────────────────────
@router.get("/history")
def history(username=Depends(verify_token)):
    user_id = get_user_id(username)
    return get_user_history(user_id)
