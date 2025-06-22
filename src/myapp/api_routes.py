import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from myapp.retriever import retrieve
from myapp.llm_interface import ask_llm_hf

router = APIRouter()


class AskRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(req: AskRequest):
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
