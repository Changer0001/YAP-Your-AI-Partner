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
    "provided document context. Only answer if you can find the answer in the history or documents. "
    "When the user says things like 'refer to previous' or 'how long does it take,' infer missing details "
    "from earlier turns. "
    "**If the answer is not explicitly found in the context or history, respond only with: 'I don't know.'** "
    "DO NOT make up or guess information under any circumstances."
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

def should_reject_answer(answer: str, doc_context: str) -> bool:
    if not answer.strip():
        return True

    hallucinated_patterns = [
        "please contact", "you can estimate", "depends on", "we recommend",
        "as a general guide", "standard shipping", "you may", "your cart", "our team",
        "visit our website", "during checkout", "language model", "I'm here to help"
    ]

    context_keywords = set(doc_context.lower().split())
    answer_words = set(answer.lower().split())
    match_ratio = len(context_keywords & answer_words) / max(len(context_keywords), 1)

    return match_ratio < 0.05 or any(p in answer.lower() for p in hallucinated_patterns)


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
        msgs.append({
            "role": "assistant",
            "content": (
                "Use ONLY the context below to answer. If the answer is not clearly found in this context, say: 'I don't know.'\n\n"
                "Context:\n" + doc_context.strip()
            )
        })
    msgs.extend(blocks_to_messages(history_blocks))
    msgs.append({
        "role": "user",
        "content": (
            "Important: Answer ONLY if the answer is clearly found in the above context or previous messages. "
            "Otherwise, say: 'I don't know.'"
        )
    })
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

    if should_reject_answer(answer, doc_context):
        logging.warning(f"🤖 Filtered hallucinated answer: {answer}")
        return "I don't know."

    return answer.strip()


def ask_llm_hf_stream(
    question: str, history_blocks: str, doc_context: str = ""
):
    if not doc_context.strip() and not history_blocks.strip():
        yield "I don't know."
        return

    msgs = make_chat_messages(history_blocks, question, doc_context)

    for attempt in range(3):
        try:
            for token in _chat_stream(msgs):
                yield token
            return  # ✅ success, stop further attempts
        except Exception as e:
            logging.warning(f"⚠️ Stream attempt {attempt + 1} failed: {e}")
            time.sleep(2 * (attempt + 1))  # exponential backoff

    # If all retries fail
    yield "I don't know."
