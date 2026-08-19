"""Chat endpoint — conversational, memory-backed, property-scoped."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services import auth
from backend.services import chat as chat_service
from backend.services.properties import current_property

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    filters: Optional[dict[str, Any]] = None


@router.post("/chat")
def chat(req: ChatRequest, user: dict = Depends(auth.require_auth),
         prop: dict = Depends(current_property)):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(400, "Question is required")
    try:
        return chat_service.chat_turn(user, req.conversation_id, question, prop)
    except Exception as exc:
        raise HTTPException(503, f"Local model error: {exc}. Is Ollama running?")
