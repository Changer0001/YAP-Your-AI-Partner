"""Pydantic request/response models."""
from typing import Any, Optional

from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    """User-supplied metadata. Blank fields stay blank — never invented."""
    site: Optional[str] = None
    department: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    doc_date: Optional[str] = None
    author: Optional[str] = None
    status: Optional[str] = None


class ChatRequest(BaseModel):
    question: str
    filters: Optional[dict[str, Any]] = None


class SearchRequest(BaseModel):
    query: str
    filters: Optional[dict[str, Any]] = None
    top_k: int = 10


class Source(BaseModel):
    n: int
    filename: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    site: Optional[str] = None
    doc_type: Optional[str] = None
    similarity: float
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = []
    mode: str  # "knowledge_base" | "no_results" | "assistant"
    intent: Optional[str] = None
    timing: dict[str, float] = {}
