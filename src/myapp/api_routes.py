from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from myapp.retriever import retrieve
from myapp.llm_interface import ask_llm_hf
from myapp.auth import verify_token, create_token, register_user, authenticate_user
from myapp.chat_store import save_chat_history, get_user_history

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
def ask(req: AskRequest, user=Depends(verify_token)):
    try:
        context = retrieve(req.question)
        print("🔍 Retrieved context:", context[:300])
        if not context.strip():
            raise HTTPException(status_code=404, detail="No relevant context found.")
        answer = ask_llm_hf(req.question, context)
        save_chat_history(user, req.question, answer)
        return {
            "question": req.question,
            "answer": answer,
            "context_snippet": context
        }
    except Exception as e:
        print(f"❌ Error in /ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
def get_history(user=Depends(verify_token)):
    return get_user_history(user)