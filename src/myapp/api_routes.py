import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal
from myapp.ingest import load_documents, ingest_and_store
from myapp.retriever import retrieve
from myapp.llm_interface import ask_llm_openai, ask_llm_hf

router = APIRouter()

class IngestRequest(BaseModel):
    folder_path: str

class AskRequest(BaseModel):
    question: str
    provider: Literal['openai', 'hf'] = 'openai'

@router.post("/ingest")
def ingest(req: IngestRequest):
    try:
        documents = load_documents(req.folder_path)
        ingest_and_store(documents)
        return {"status": "success", "documents_ingested": len(documents)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
