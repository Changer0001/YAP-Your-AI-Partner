# app/api/api_routes.py
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
import logging
from sqlalchemy.orm import Session
import json


from app.db.database import get_db
from app.api.auth import verify_token, register_user, authenticate_user
from app.core.utils import get_user_id
from app.db.chat_store import save_chat_history, get_user_history, get_recent_history
from app.llm.llm_interface import ask_llm_hf, ask_llm_hf_stream, format_history_blocks
from app.core.token_utils import allocate_token_budget
from app.retriever.rrf_hyde import build_context_from_collection

router = APIRouter()
logging.basicConfig(level=logging.INFO)

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
        if rows:
            logging.info(f"[retrieval:/ask] first_preview={(rows[0][1] or '')[:120]}")

    

        # 4) Convert history to the LLM's expected format
        # REMOVE the allocate_token_budget block and set these two lines instead:
        history_blocks = format_history_blocks(history_dicts)
        doc_context_str = ctx  # pass the fused context directly


        # 5) Ask the LLM grounded on the built context
        answer = ask_llm_hf(
            question=req.question,
            history_blocks=history_blocks,
            doc_context=doc_context_str,   # pass fused context string
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
        if rows:
            logging.info(f"[retrieval:/ask_stream] first_preview={(rows[0][1] or '')[:120]}")

        # 3) Token budget (prevents overflow)
        

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
