from typing import List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from starlette.responses import StreamingResponse
import logging
from sqlalchemy.orm import Session
import json
from myapp.chroma_config import client

from .database import get_db
from myapp.auth import verify_token, register_user, authenticate_user
from myapp.utils import get_user_id
from myapp.chat_store import save_chat_history, get_user_history, get_recent_history
from myapp.retriever import retrieve
from myapp.llm_interface import ask_llm_hf, ask_llm_hf_stream, format_history_blocks


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
    history: List[HistoryEntry] = []  # ✅ Proper model type here


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
    try:
        user_id = get_user_id(username)
        history = req.history or get_recent_history(user_id)
        context = format_history_blocks([h.dict() for h in history])
        doc_ctx = retrieve(req.question)

        if not doc_ctx.strip() and not context.strip():
            answer = "I don't know."
        else:
            answer = ask_llm_hf(req.question, context, doc_ctx)

        save_chat_history(user_id, req.question, answer)
        return {"question": req.question, "answer": answer}
    except Exception as e:
        logging.exception("❌ /ask failed:")
        raise HTTPException(status_code=500, detail=str(e))

# ── /ask/stream ───────────────────────────────────────────────────────
@router.post("/ask/stream")
async def stream(req: AskRequest, username=Depends(verify_token)):
    logging.info("📩 Received payload: %s", req.dict())
    logging.info("🧪 Received AskRequest payload: %s", req.dict())

    try:
        user_id = get_user_id(username)
        history = req.history or get_recent_history(user_id)
        context = format_history_blocks(history)
        doc_ctx = retrieve(req.question)

        logging.info("🔍 Streaming context snippet: %s", doc_ctx[:120])

        def generator():
            full_answer = ""
            try:
                for token in ask_llm_hf_stream(req.question, context, doc_ctx):
                    full_answer += token
                    yield token
            except Exception as e:
                logging.exception("❌ Stream error:")
                yield f"\n[ERROR] {e}"
            finally:
                save_chat_history(user_id, req.question, full_answer)

        return StreamingResponse(generator(), media_type="text/plain")

    except Exception as e:
        logging.exception("❌ /ask/stream failed:")
        return StreamingResponse(iter([f"[ERROR] {e}"]), media_type="text/plain")

# ── /history ──────────────────────────────────────────────────────────
@router.get("/history")
def history(username=Depends(verify_token)):
    user_id = get_user_id(username)
    return get_user_history(user_id)
