import logging
from typing import List, Optional, Union

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from myapp.auth        import verify_token, register_user, authenticate_user
from myapp.utils       import get_user_id
from myapp.chat_store  import save_chat_history, get_user_history, get_recent_history
from myapp.retriever   import retrieve
from myapp.llm_interface import (
    ask_llm_hf,
    ask_llm_hf_stream,
    format_history_blocks,   # converts list[dict] → “🧑 Q / 🤖 A” blocks
)

router = APIRouter()
logging.basicConfig(level=logging.INFO)

# ── Helper ────────────────────────────────────────────────────────────────────
def parse_history(raw_history: Union[List[str], List[dict]]) -> List[dict]:
    """
    Accepts either:
      • legacy list[str]  like "🧑 Q: …", "🤖 A: …"
      • new   list[dict]  like {"role": "user", "content": …}
    Returns list[dict] in the new format.
    """
    if not raw_history:
        return []

    if isinstance(raw_history[0], str):            # legacy blocks
        parsed: List[dict] = []
        for entry in raw_history:
            if entry.startswith("🧑 Q:"):
                parsed.append({"role": "user", "content": entry.replace("🧑 Q:", "").strip()})
            elif entry.startswith("🤖 A:"):
                parsed.append({"role": "assistant", "content": entry.replace("🤖 A:", "").strip()})
        return parsed
    return raw_history                              # already structured


# ── Request / response models ─────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None

class AskRequest(BaseModel):
    question: str
    history: Optional[List[Message] | List[str]] = None


# ── Auth endpoints ────────────────────────────────────────────────────────────
@router.post("/register")
def register(req: RegisterRequest):
    if not register_user(req.username, req.password):
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"message": "User registered successfully"}

@router.post("/login")
def login(req: LoginRequest):
    token = authenticate_user(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": token}


# ── /ask (blocking) ───────────────────────────────────────────────────────────
@router.post("/ask")
def ask(req: AskRequest, username=Depends(verify_token)):
    try:
        user_id  = get_user_id(username)
        history  = parse_history(req.history or get_recent_history(user_id))
        context  = format_history_blocks(history)
        doc_ctx  = retrieve(req.question)

        if not doc_ctx.strip() and not context.strip():
            answer = "I don't know."
        else:
            answer = ask_llm_hf(req.question, context, doc_ctx)

        save_chat_history(user_id, req.question, answer)
        return {"question": req.question, "answer": answer}

    except Exception as e:
        logging.exception("❌ /ask failed:")
        raise HTTPException(status_code=500, detail=str(e))


# ── /ask/stream (streaming) ──────────────────────────────────────────────────
@router.post("/ask/stream")
async def stream(req: AskRequest, username=Depends(verify_token)):
    try:
        user_id  = get_user_id(username)
        history  = parse_history(req.history or get_recent_history(user_id))
        context  = format_history_blocks(history)
        doc_ctx  = retrieve(req.question)

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


# ── /history ─────────────────────────────────────────────────────────────────
@router.get("/history")
def history(username=Depends(verify_token)):
    user_id = get_user_id(username)
    return get_user_history(user_id)
