import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from myapp.auth        import verify_token, register_user, authenticate_user
from myapp.utils       import get_user_id
from myapp.chat_store  import save_chat_history, get_user_history, get_recent_history
from myapp.retriever   import retrieve
from myapp.llm_interface import ask_llm_hf, ask_llm_hf_stream

router = APIRouter()
logging.basicConfig(level=logging.INFO)

# ── Request/response models ───────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AskRequest(BaseModel):
    question: str


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
        user_id = get_user_id(username)

        # 1. personal chat history
        history_context  = "\n".join(get_recent_history(user_id))

        # 2. retrieved docs specific to this question
        document_context = retrieve(req.question)

        answer = ask_llm_hf(
            req.question,
            history_context,
            document_context        # <-- now passed correctly
        )

        save_chat_history(user_id, req.question, answer)
        return {
            "question": req.question,
            "answer":   answer
        }

    except Exception as e:
        logging.exception("❌ /ask failed:")
        raise HTTPException(status_code=500, detail=str(e))


# ── /ask/stream (streaming) ──────────────────────────────────────────────────
@router.post("/ask/stream")
async def stream(req: AskRequest, username=Depends(verify_token)):
    user_id          = get_user_id(username)
    history_context  = "\n".join(get_recent_history(user_id))
    document_context = retrieve(req.question)

    logging.info("🔍 Streaming context snippet: %s", document_context[:120])

    def generator():
        full_answer = ""
        try:
            for token in ask_llm_hf_stream(
                    req.question,
                    history_context,
                    document_context):
                full_answer += token
                yield token
        except Exception as e:
            logging.exception("❌ Stream error:")
            yield f"\n[ERROR] {e}"
        finally:
            save_chat_history(user_id, req.question, full_answer)

    return StreamingResponse(generator(), media_type="text/plain")


# ── /history ─────────────────────────────────────────────────────────────────
@router.get("/history")
def history(username=Depends(verify_token)):
    user_id = get_user_id(username)
    return get_user_history(user_id)
