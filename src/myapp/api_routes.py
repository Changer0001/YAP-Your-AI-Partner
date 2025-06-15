import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal
from myapp.retriever import retrieve
from myapp.llm_interface import ask_llm_openai, ask_llm_hf

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    provider: Literal['openai', 'hf'] = 'openai'


@router.post("/ask")
def ask(req: AskRequest):
    try:
        context = retrieve(req.question)
        if not context:
            raise HTTPException(status_code=404, detail="No relevant context found.")

        if req.provider == 'hf':
            answer = ask_llm_hf(req.question, context)
        else:
            answer = ask_llm_openai(req.question, context)

        return {
            "question": req.question,
            "answer": answer,
            "context_snippet": context
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
