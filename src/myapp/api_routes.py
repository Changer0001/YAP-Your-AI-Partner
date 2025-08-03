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
from myapp.llm_core import _chat_once, _chat_stream, enforce_alternating_roles


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
        history_blocks = format_history_blocks(history)

        doc_ctx = retrieve(req.question)
        answer = ask_llm_hf(req.question, history_blocks, doc_ctx, user_id)

        save_chat_history(user_id, req.question, answer)
        return {"question": req.question, "answer": answer}

    except Exception as e:
        logging.exception("❌ /ask failed:")
        raise HTTPException(status_code=500, detail=str(e))
    





# ── /ask/stream ───────────────────────────────────────────────────────
@router.post("/ask/stream")
async def stream(req: AskRequest, username=Depends(verify_token)):
    try:
        user_id = get_user_id(username)
        history = req.history or get_recent_history(user_id)
        history_blocks = format_history_blocks(history)

        doc_ctx = retrieve(req.question)

        print("🧪 Calling ask_llm_hf_stream() with question:", req.question)
        print("🧪 doc_ctx length:", sum(len(chunk) for chunk in doc_ctx))

        if isinstance(history_blocks, list) and all(isinstance(h, dict) and 'content' in h for h in history_blocks):
            print("🧪 history_blocks length:", sum(len(h['content']) for h in history_blocks))
        else:
            print("⚠️ Unexpected history_blocks structure:", history_blocks)


        def generator():    
            print("🧪 Entered generator()")
            full_answer = ""
            try:
                print("🧪 Entered generator()")  # NEW
                stream = ask_llm_hf_stream(req.question, history_blocks, doc_ctx, user_id)
                print("🧪 Got stream from ask_llm_hf_stream()")  # NEW

                for token in stream:
                    print("🔹 Streaming token:", token)
                    full_answer += token
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': token}}]})}\n\n"
                print("✅ Streaming finished.")  # NEW

            except Exception as e:
                print("❌ Stream error:", e)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                save_chat_history(user_id, req.question, full_answer)


        return StreamingResponse(generator(), media_type="text/event-stream")

    except Exception as e:
        print("❌ /ask/stream failed:", e)
        return StreamingResponse(iter([f"data: {json.dumps({'error': str(e)})}\n\n"]), media_type="text/event-stream")





# ── /history ──────────────────────────────────────────────────────────
@router.get("/history")
def history(username=Depends(verify_token)):
    user_id = get_user_id(username)
    return get_user_history(user_id)
