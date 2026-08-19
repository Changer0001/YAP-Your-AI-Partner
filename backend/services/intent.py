"""Intent router — decide what a message needs BEFORE any knowledge retrieval.

Greetings, small talk, and identity questions are answered naturally and deterministically from
application configuration (never from documents, never invented). "What did we discuss…" style
questions are flagged for conversation recall. Everything else is a knowledge query.
"""
import re
from dataclasses import dataclass
from typing import Optional

from backend.config import settings

# intent types
GREETING = "greeting"
CASUAL = "casual"
IDENTITY = "identity"
FOUNDER = "founder"
MEANING = "meaning"
CAPABILITIES = "capabilities"
RECALL = "conversation_recall"
KNOWLEDGE = "knowledge_query"

DETERMINISTIC = {GREETING, CASUAL, IDENTITY, FOUNDER, MEANING, CAPABILITIES}


@dataclass
class Intent:
    type: str
    response: Optional[str] = None  # filled for deterministic intents


_GREETING = re.compile(r"^\s*(hi|hello|hey|yo|hiya|good\s*(morning|afternoon|evening|day)|greetings)\b", re.I)
_CASUAL = re.compile(r"\b(how\s+are\s+you|how'?s\s+it\s+going|what'?s\s+up|how\s+do\s+you\s+do|"
                     r"thank(s| you)|thx|appreciate\s+it|good\s*(bye|night)|see\s+you|nice\s+to\s+meet)\b", re.I)
_MEANING = re.compile(r"\b(what\s+does\s+yap\s+stand\s+for|what\s+does\s+yap\s+mean|what\s+is\s+yap\b)", re.I)
_FOUNDER = re.compile(r"\b(who\s+(founded|created|made|built|owns|developed)\b|"
                      r"who(\s+is|'?s)\s+(your|the)\s+(founder|creator|owner|maker)|"
                      r"who\s+is\s+behind\s+(you|yap)|your\s+founder|founder\s+of\s+yap)\b", re.I)
_IDENTITY = re.compile(r"\b(who\s+are\s+you|what\s+are\s+you|your\s+name|are\s+you\s+(an?\s+)?(ai|bot|assistant))\b", re.I)
_CAPS = re.compile(r"\b(what\s+can\s+you\s+do|what\s+do\s+you\s+do|how\s+can\s+you\s+help|how\s+do\s+you\s+work|"
                   r"what\s+are\s+you\s+(for|capable)|help\s+me\s+with\s+what)\b", re.I)
_RECALL = re.compile(r"\b(what\s+did\s+we\s+(discuss|talk|say)|what\s+did\s+i\s+(say|tell|give|mention)|"
                     r"(earlier|before|yesterday|previously|last\s+time)\b.*\b(discuss|say|said|tell|told|mention|talk)|"
                     r"remind\s+me\s+what|what\s+was\s+the\s+.*\bi\s+(gave|told|mentioned)|"
                     r"do\s+you\s+remember|what\s+ip\s+did\s+i)\b", re.I)


def _identity_text() -> str:
    return (f"I'm {settings.yap_name} — {settings.yap_full_name}. I'm a local AI assistant designed to "
            "help you work with your knowledge, find information, and have natural conversations.")


def _capabilities_text() -> str:
    return (f"I'm {settings.yap_name}, your local AI assistant. Right now I can chat naturally, remember the "
            "context of our conversation, and answer questions from your indexed knowledge (documents, "
            "configs, notes, and pasted messages) — always showing the sources. Everything runs locally on "
            "your machine.")


def classify(message: str) -> Intent:
    text = (message or "").strip()
    if not text:
        return Intent(KNOWLEDGE)
    # Identity/meaning/founder take priority over a leading greeting ("hi, who are you?").
    if _FOUNDER.search(text):
        return Intent(FOUNDER, f"{settings.yap_name} was founded by {settings.yap_founder.rstrip('.')}.")
    if _MEANING.search(text) or re.search(r"\bwhat\s+is\s+yap\b", text, re.I):
        return Intent(MEANING, f"{settings.yap_name} stands for {settings.yap_full_name}. It's a local AI "
                               "assistant that helps you find information, work with your knowledge, and have "
                               "natural conversations.")
    if _IDENTITY.search(text):
        return Intent(IDENTITY, _identity_text())
    if _CAPS.search(text):
        return Intent(CAPABILITIES, _capabilities_text())
    if _RECALL.search(text):
        return Intent(RECALL)
    if _GREETING.search(text) and len(text.split()) <= 7:
        return Intent(GREETING, "Hello! How can I help you today?")
    if _CASUAL.search(text) and len(text.split()) <= 8:
        if re.search(r"\bthank", text, re.I):
            return Intent(CASUAL, "You're welcome!")
        if re.search(r"\bhow\s+are\s+you|how'?s\s+it\s+going|how\s+do\s+you\s+do", text, re.I):
            return Intent(CASUAL, "I'm doing well, thanks! What are we working on today?")
        if re.search(r"\bgood\s*(bye|night)|see\s+you", text, re.I):
            return Intent(CASUAL, "Take care! I'll be here when you need me.")
        return Intent(CASUAL, "Happy to help — what would you like to work on?")
    return Intent(KNOWLEDGE)
