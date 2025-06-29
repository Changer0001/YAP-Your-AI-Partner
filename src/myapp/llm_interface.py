import os
import re
import time
import logging
from typing import List, Dict, Any

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# ── Init ──────────────────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(filename="app.log", filemode="a", level=logging.DEBUG)

HF_API_TOKEN = os.getenv("HF_API_TOKEN")
client = InferenceClient(
    model="mistralai/Mistral-7B-Instruct-v0.2",
    token=HF_API_TOKEN,
)

SYSTEM_INSTRUCTION = (
    "You are a helpful assistant. Use the ENTIRE conversation history plus any "
    "provided document context. When the user says things like "
    "‘refer to previous’ or ‘how long does it take,’ infer missing details "
    "(item, origin, destination, weight, dates) from earlier turns. "
    "If the answer is not in context, reply with: I don't know."
)

_INCOMPLETE_RE = re.compile(r"\b(and|but|or|so|because)$", re.IGNORECASE)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _is_incomplete(text: str) -> bool:
    text = text.strip()
    return (
        not text
        or text[-1] not in ".!?"
        or text.endswith("...")
        or _INCOMPLETE_RE.search(text)
    )


def format_history_blocks(history: List[Any]) -> str:
    """Convert list[{role, content}] or Message objects → multiline blocks 🧑 Q / 🤖 A."""
    lines: List[str] = []
    for m in history[-16:]:  # last 8 Q/A pairs
        role = m.role if hasattr(m, "role") else m["role"]
        content = m.content if hasattr(m, "content") else m["content"]
        tag = "🧑 Q:" if role == "user" else "🤖 A:"
        lines.append(f"{tag} {content.strip()}")
    return "\n".join(lines)


def blocks_to_messages(blocks: str) -> List[Dict[str, str]]:
    """Convert 🧑 Q / 🤖 A blocks → messages for chat_completion."""
    msgs: List[Dict[str, str]] = []
    for line in blocks.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("🧑 Q:"):
            msgs.append({"role": "user", "content": line[5:].strip()})
        elif line.startswith("🤖 A:"):
            msgs.append({"role": "assistant", "content": line[5:].strip()})
    return msgs


def make_chat_messages(
    history_blocks: str, question: str, doc_context: str = ""
) -> List[Dict[str, str]]:
    """Create chat-compatible message list with system instruction and context."""
    msgs: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    if doc_context.strip():
        msgs.append(
            {"role": "assistant", "content": "Context:\n" + doc_context.strip()}
        )
    msgs.extend(blocks_to_messages(history_blocks))
    msgs.append({"role": "user", "content": question})
    return msgs[-30:]  # keep within token limits


# ── Core wrappers ─────────────────────────────────────────────────────────────
def _chat_once(
    messages: List[Dict[str, str]],
    max_tokens: int = 300,
    temperature: float = 0.7,
) -> str:
    try:
        start = time.time()
        res = client.chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        logging.info("⏱️ chat time %.2fs", time.time() - start)
        return res.choices[0].message.content.strip()
    except Exception as e:
        logging.exception("❌ chat_completion failed:")
        return f"Error: {e}"


def _chat_stream(
    messages: List[Dict[str, str]],
    max_tokens: int = 300,
    temperature: float = 0.7,
):
    try:
        stream = client.chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and hasattr(chunk.choices[0], "delta"):
                delta = chunk.choices[0].delta
                if isinstance(delta, dict) and "content" in delta:
                    yield delta["content"]
    except Exception as e:
        logging.exception("❌ chat stream failed:")
        yield f"\n[ERROR] {e}"


# ── Public API (used in api_routes.py) ────────────────────────────────────────
def ask_llm_hf(
    question: str, history_blocks: str, doc_context: str = ""
) -> str:
    msgs = make_chat_messages(history_blocks, question, doc_context)
    answer = _chat_once(msgs)
    if _is_incomplete(answer):
        msgs.append({"role": "assistant", "content": answer})
        msgs.append({"role": "user", "content": "Continue:"})
        answer += " " + _chat_once(msgs, max_tokens=120)
    return answer.strip()


def ask_llm_hf_stream(
    question: str, history_blocks: str, doc_context: str = ""
):
    msgs = make_chat_messages(history_blocks, question, doc_context)
    for token in _chat_stream(msgs):
        yield token
