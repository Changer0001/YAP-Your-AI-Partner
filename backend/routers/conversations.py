"""Conversation management — strictly per-user. Every route derives user_id from the auth token,
and the store filters on it, so a user can only ever see or change their own conversations.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services import auth, conversations

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class NewConv(BaseModel):
    title: Optional[str] = None


class RenameConv(BaseModel):
    title: str


@router.get("")
def list_conversations(user: dict = Depends(auth.require_auth)):
    return conversations.list_for(user["username"])


@router.post("")
def create_conversation(body: NewConv, user: dict = Depends(auth.require_auth)):
    return conversations.create(user["username"], (body.title or "New conversation").strip() or "New conversation")


@router.get("/search")
def search_conversations(q: str, user: dict = Depends(auth.require_auth)):
    return conversations.search(user["username"], q)


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str, user: dict = Depends(auth.require_auth)):
    conv = conversations.get(conversation_id, user["username"])
    if not conv:
        raise HTTPException(404, "Conversation not found")
    conv["messages"] = conversations.messages(conversation_id, user["username"])
    return conv


@router.patch("/{conversation_id}")
def rename_conversation(conversation_id: str, body: RenameConv, user: dict = Depends(auth.require_auth)):
    if not conversations.rename(conversation_id, user["username"], body.title):
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str, user: dict = Depends(auth.require_auth)):
    if not conversations.delete(conversation_id, user["username"]):
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}
