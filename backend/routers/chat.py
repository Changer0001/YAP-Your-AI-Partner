"""Chat endpoint — grounded answers with citations."""
from fastapi import APIRouter, HTTPException

from backend.models import ChatRequest, ChatResponse
from backend.services import chat as chat_service

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(400, "Question is required")
    try:
        return chat_service.answer(question, req.filters)
    except Exception as exc:
        raise HTTPException(503, f"Local model error: {exc}. Is Ollama running?")
