from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from myapp.retriever import retrieve
from myapp.llm_interface import ask_llm_hf, ask_llm_hf_stream
from myapp.auth import verify_token, create_token, register_user, authenticate_user
from myapp.chat_store import save_chat_history, get_user_history
from myapp.utils import get_user_id  # 🔹 Add this import
from starlette.responses import StreamingResponse
import logging

router = APIRouter()

# --- Models ---
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AskRequest(BaseModel):
    question: str

# --- Register ---
@router.post("/register")
def register(req: RegisterRequest):
    success = register_user(req.username, req.password)
    if not success:
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"message": "User registered successfully"}

# --- Login ---
@router.post("/login")
def login(req: LoginRequest):
    token = authenticate_user(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": token}

# --- Ask (protected) ---
@router.post("/ask")
def ask(req: AskRequest, username=Depends(verify_token)):
    try:
        user_id = get_user_id(username)  # 🔹 Convert to user_id
        context = retrieve(req.question)
        logging.info("🔍 Retrieved context: %s", context[:300])
        if not context.strip():
            raise HTTPException(status_code=404, detail="No relevant context found.")
        answer = ask_llm_hf(req.question, context)
        save_chat_history(user_id, req.question, answer)  # 🔹 Save with user_id
        return {
            "question": req.question,
            "answer": answer,
            "context_snippet": context
        }
    except Exception as e:
        logging.error("❌ Error in /ask: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

# --- Streaming Ask ---
@router.post("/ask/stream")
async def stream(req: AskRequest, username=Depends(verify_token)):
    user_id = get_user_id(username)  # 🔹 Convert to user_id
    context = retrieve(req.question)
    logging.info(f"🔍 Streaming context: {context[:300]}")

    def generate():
        full_answer = ""
        try:
            for chunk in ask_llm_hf_stream(req.question, context):
                token = chunk if isinstance(chunk, str) else getattr(chunk, "content", "")
                full_answer += token
                yield token
        except Exception as e:
            logging.error(f"❌ Stream error: {e}")
            yield f"\n[ERROR] {e}"
        finally:
            save_chat_history(user_id, req.question, full_answer)  # 🔹 Save with user_id

    return StreamingResponse(generate(), media_type="text/plain")

# --- History ---
@router.get("/history")
def get_history(username=Depends(verify_token)):
    user_id = get_user_id(username)  # 🔹 Convert to user_id
    return get_user_history(user_id)  # 🔹 Retrieve by user_id
