import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from myapp.retriever import retrieve
from myapp.llm_interface import ask_llm_hf
from myapp.auth import verify_token, create_token
from passlib.context import CryptContext

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ✅ Temporary in-memory user "database"
fake_users_db = {}

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
    if req.username in fake_users_db:
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed_pw = pwd_context.hash(req.password)
    fake_users_db[req.username] = hashed_pw
    return {"message": "User registered successfully"}

# --- Login ---
@router.post("/login")
def login(req: LoginRequest):
    stored_pw = fake_users_db.get(req.username)
    if not stored_pw or not pwd_context.verify(req.password, stored_pw):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user_id=req.username)
    return {"access_token": token}

# --- Ask (protected) ---
@router.post("/ask")
def ask(req: AskRequest, user=Depends(verify_token)):
    try:
        context = retrieve(req.question)
        if not context:
            raise HTTPException(status_code=404, detail="No relevant context found.")
        answer = ask_llm_hf(req.question, context)
        return {
            "question": req.question,
            "answer": answer,
            "context_snippet": context
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
