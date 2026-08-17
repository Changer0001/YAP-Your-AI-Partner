"""Intent router — decide whether a message needs the knowledge base at all.

Greetings, small talk, and identity questions are answered **deterministically** from application
configuration (never from company documents, never from the LLM inventing an owner). Everything
else is treated as a knowledge query and goes through RAG.
"""
import re
from dataclasses import dataclass

from backend.config import settings

KNOWLEDGE = "knowledge_query"


@dataclass
class Intent:
    type: str                 # greeting | identity | capabilities | knowledge_query
    response: str | None = None  # deterministic reply for non-knowledge intents


_GREETING = re.compile(
    r"^\s*(hi|hello|hey|yo|good\s*(morning|afternoon|evening)|how\s+are\s+you|"
    r"what'?s\s+up|thanks|thank\s+you|bye|goodbye)\b", re.I)
_IDENTITY = re.compile(
    r"\b(who\s+are\s+you|what\s+are\s+you|your\s+name|who\s+(made|created|built|owns?|"
    r"is\s+your\s+owner)|who\s+do\s+you\s+belong)\b", re.I)
_CAPABILITIES = re.compile(
    r"\b(what\s+can\s+you\s+do|what\s+do\s+you\s+do|how\s+do\s+you\s+work|"
    r"help|how\s+can\s+you\s+help|what\s+are\s+you\s+for)\b", re.I)


def _identity_text() -> str:
    org = f" for {settings.org_name}" if settings.org_name else ""
    return (f"I'm **{settings.assistant_name}**, a local, private IT assistant{org}. "
            f"I'm maintained by {settings.assistant_owner}, and I run entirely on this machine — "
            "your documents never leave it. I answer from your indexed IT documentation and always "
            "show my sources.")


def _capabilities_text() -> str:
    return (f"I answer questions from your indexed IT documentation (SOPs, network docs, configs, "
            "PDFs, Word/Excel, notes) using local RAG, and I cite the source of every answer. "
            "You can add documents in the **Documents** tab, inspect the index in **Search**, and "
            "if I can't find something in your documents I'll tell you rather than guess.")


def classify(message: str) -> Intent:
    text = (message or "").strip()
    # Identity/capabilities take priority over a leading greeting ("hi, who are you?").
    if _IDENTITY.search(text):
        return Intent("identity", _identity_text())
    if _CAPABILITIES.search(text):
        return Intent("capabilities", _capabilities_text())
    if _GREETING.search(text) and len(text.split()) <= 6:
        return Intent("greeting",
                      f"Hello! I'm **{settings.assistant_name}**. Ask me about your indexed IT "
                      "documentation, or add documents in the Documents tab.")
    return Intent(KNOWLEDGE)
