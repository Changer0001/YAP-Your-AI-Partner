# myapp/api_routes.py
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import logging
from sqlalchemy.orm import Session
import json
from app.core.chroma_config import client

from app.db.database import get_db
from app.api.auth import verify_token, register_user, authenticate_user
from app.core.utils import get_user_id
from app.db.chat_store import save_chat_history, get_user_history, get_recent_history
from app.retriever.retriever import retrieve
from app.llm.llm_interface import ask_llm_hf, ask_llm_hf_stream, format_history_blocks
from app.core.token_utils import allocate_token_budget

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

        doc_chunks = retrieve(req.question)
        for i, chunk in enumerate(doc_chunks):
            logging.debug(f"📄 Final Chunk {i+1}: {chunk[:120]}...")
        answer = ask_llm_hf(req.question, history_blocks, doc_chunks, user_id)

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

        history_blocks = (
            [h.model_dump() for h in req.history]
            if req.history else get_recent_history(user_id)
        )

        doc_chunks = retrieve(req.question)

        
        trimmed_messages, trimmed_docs = allocate_token_budget(
            messages=history_blocks,
            doc_chunks=doc_chunks,
            max_total_tokens=4096,
            reserved_completion=300,
            verbose=True
        )



        # 🔁 Define normal (sync) generator — this is valid for StreamingResponse
        def generator():
            print("🧪 Entered generator()")
            full_answer = ""
            try:
                stream = ask_llm_hf_stream(req.question, trimmed_messages, trimmed_docs, user_id)
                print("🧪 Got stream from ask_llm_hf_stream()")

                for token in stream:
                    print("🔹 Streaming token:", token)
                    full_answer += token
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': token}}]})}\n\n"

                print("✅ Streaming finished.")

            except Exception as e:
                print("❌ Stream error:", e)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            finally:
                print("💾 Saving history...")
                save_chat_history(user_id, req.question, full_answer)

        # ✅ Proper usage with StreamingResponse
        return StreamingResponse(generator(), media_type="text/event-stream")

    except Exception as e:
        print("❌ /ask/stream failed:", e)
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': str(e)})}\n\n"]),
            media_type="text/event-stream"
        )





# ── /history ──────────────────────────────────────────────────────────
@router.get("/history")
def history(username=Depends(verify_token)):
    user_id = get_user_id(username)
    return get_user_history(user_id)
