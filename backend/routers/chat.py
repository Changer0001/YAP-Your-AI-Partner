"""Chat endpoint — grounded answers with citations, scoped to the caller's property."""
from fastapi import APIRouter, Depends, HTTPException

from backend.models import ChatRequest, ChatResponse
from backend.services import chat as chat_service
from backend.services.properties import current_property

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, prop: dict = Depends(current_property)):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(400, "Question is required")
    try:
        return chat_service.answer(prop["collection"], question, req.filters)
    except Exception as exc:
        raise HTTPException(503, f"Local model error: {exc}. Is Ollama running?")
