# app/llm/llm_interface.py
import os, re, time, json, logging
from typing import List, Dict, Any, Union, Generator, Optional
from dotenv import load_dotenv

load_dotenv(override=True)  # ensure .env overrides any existing env

from app.db.memory_store import Memory
from app.db.database import SessionLocal
from app.llm.llm_core import _chat_once, _chat_stream, enforce_alternating_roles
from app.core.token_utils import count_tokens
from app.retriever.intent_classifier import classify_intent

# ---- env + constants ---------------------------------------------------------
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_TOKENS", "32768"))
RESERVED_COMPLETION = int(os.getenv("RESERVED_COMPLETION", "1536"))

VLLM_API_URL = os.getenv("VLLM_API_URL")
if not VLLM_API_URL:
    raise RuntimeError("VLLM_API_URL env var missing!")

MODEL_NAME = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

logging.basicConfig(filename="app.log", filemode="a", level=logging.DEBUG)

SYSTEM_INSTRUCTION = (
    "You are a helpful assistant.\n"
    "- If the user is greeting / small talk, respond naturally and briefly.\n"
    "- For business/policy questions, use ONLY the provided context. "
    "If the answer is not clearly in the context, say: 'I don't know.' Do NOT guess.\n"
    "- Prefer concise bullet lists when applicable."
)

_SMALLTALK = {"greeting", "goodbye", "thank_you"}
_NAME_RE = re.compile(r"\b(?:i am|i'm|this is|it is)\s+([A-Za-z][\w'-]+)\b", re.I)
_INCOMPLETE_RE = re.compile(r"\b(and|but|or|so|because)$", re.IGNORECASE)

_GREETING_RX  = re.compile(r"\b(hi|hey|hello|good (morning|afternoon|evening))\b", re.I)
_THANKS_RX    = re.compile(r"\b(thanks|thank you|appreciate(d)?|much appreciated)\b", re.I)
_GOODBYE_RX   = re.compile(r"\b(bye|good night|see you|take care)\b", re.I)
_HOWAREYOU_RX = re.compile(r"\b(how (are|r) (you|u)|how’s it going|how are things)\b", re.I)

def _is_smalltalk_text(text: str) -> bool:
    t = (text or "").strip()
    return bool(
        _GREETING_RX.search(t)
        or _THANKS_RX.search(t)
        or _GOODBYE_RX.search(t)
        or _HOWAREYOU_RX.search(t)
    )

SMALLTALK_GREET  = "Hey{who}! How can I help today?"
SMALLTALK_THANKS = "You’re welcome! Anything else I can do?"
SMALLTALK_GOODBYE= "Take care! Ping me anytime."
SMALLTALK_HRU    = "I’m doing well—thanks for asking{who}! How can I help?"

def _smalltalk_reply(question: str, name: Optional[str]) -> str:
    who = f", {name}" if name else ""
    if _THANKS_RX.search(question):  return SMALLTALK_THANKS
    if _GOODBYE_RX.search(question): return SMALLTALK_GOODBYE
    if _HOWAREYOU_RX.search(question): return SMALLTALK_HRU.format(who=who)
    return SMALLTALK_GREET.format(who=who)

# ---- helpers -----------------------------------------------------------------
def _extract_name(text: str) -> Optional[str]:
    m = _NAME_RE.search(text or "")
    return m.group(1) if m else None

def _save_memory(user_id: Optional[int], topic: str, summary: str) -> None:
    if not user_id:
        return
    db = SessionLocal()
    try:
        db.add(Memory(user_id=user_id, topic=topic, summary=summary))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

def fetch_user_memory(user_id: int, limit: int = 3) -> str:
    db = SessionLocal()
    memories = (
        db.query(Memory)
        .filter(Memory.user_id == user_id)
        .order_by(Memory.timestamp.desc())
        .limit(limit)
        .all()
    )
    db.close()
    return "\n".join(f"- {m.topic}: {m.summary}" for m in memories)

def _is_incomplete(text: str) -> bool:
    text = text.strip()
    return not text or text[-1] not in ".!?" or text.endswith("...") or _INCOMPLETE_RE.search(text)

STOP = set("""
a an the and or but if while to for of on in at from by with as into over under between
this that those these is are was were be been being do does did so such it its we our you your they their
i me my us them then than about above below again further once here there when where why how all any both each few more most
other some own same can will just don don t shouldn should wouldn would couldn could haven have hasn has hadn had
""".split())

def _tokens(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9']+", s.lower()) if w not in STOP and len(w) > 2}

def should_reject_answer(answer: str, doc_context: str, intent: Optional[str] = None) -> bool:
    """Reject ungrounded answers when grounding is expected."""
    if not answer.strip(): return True
    if intent in _SMALLTALK: return False
    if not doc_context.strip(): return True  # no grounding -> reject

    aw = _tokens(answer)
    cw = _tokens(doc_context)
    if not aw or not cw: return True
    jacc = len(aw & cw) / max(len(aw | cw), 1)

    # require meaningful overlap
    if jacc < 0.08:
        logging.warning(f"🚫 Rejected: low context overlap jacc={jacc:.3f}")
        return True
    return False

def format_history_blocks(history: List[Any]) -> str:
    lines: List[str] = []
    for m in history[-16:]:
        role = m.role if hasattr(m, "role") else m["role"]
        content = m.content if hasattr(m, "content") else m["content"]
        tag = "🧑 Q:" if role == "user" else "🤖 A:"
        lines.append(f"{tag} {content.strip()}")
    return "\n".join(lines)

def blocks_to_messages(blocks: str) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = []
    last_role = None
    for line in blocks.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("🧑 Q:"):
            role = "user"; content = line[5:].strip()
        elif line.startswith("🤖 A:"):
            role = "assistant"; content = line[5:].strip()
            if content.startswith("[ERROR]"):
                continue
        else:
            continue
        if role == last_role:
            continue
        msgs.append({"role": role, "content": content})
        last_role = role
    return msgs

def make_chat_messages(history_blocks: str, question: str, doc_context: str = "", user_id: Optional[int] = None) -> List[Dict[str, str]]:
    intent = classify_intent(question)
    system_content = SYSTEM_INSTRUCTION

    if doc_context.strip() and intent not in _SMALLTALK:
        system_content += (
            "\n\nUse ONLY the context below to answer. If the answer is not clearly and directly found, "
            "say: 'I don't know.' Do NOT guess.\n\nContext:\n" + doc_context.strip()
        )

    if user_id:
        memory_context = fetch_user_memory(user_id)
        if memory_context:
            system_content += "\n\nAdditional memory from previous sessions:\n" + memory_context

    msgs: List[Dict[str, str]] = [{"role": "system", "content": system_content}]
    history_msgs = blocks_to_messages(history_blocks)
    msgs.extend(history_msgs)

    msgs.append({
        "role": "user",
        "content": (
            f"{question.strip()}\n\n"
            "Important:\n"
            "1️⃣ Only answer if the info is in context or chat history; else say: I don't know.\n"
            "2️⃣ Format the answer as a list if applicable."
        )
    })

    msgs = enforce_alternating_roles(msgs)
    logging.debug("📦 Final messages to LLM:\n%s", json.dumps(msgs, indent=2))
    return msgs[-30:]

def truncate_messages(messages, max_tokens=MAX_CONTEXT_TOKENS, reserved_completion=RESERVED_COMPLETION):
    if not messages or len(messages) < 2:
        return messages

    system_msg = messages[0]
    rest = messages[1:]
    total_tokens = count_tokens(system_msg["content"])
    truncated: List[Dict[str, str]] = []

    # Reverse through messages, skipping system
    for msg in reversed(rest):
        msg_tokens = count_tokens(msg["content"])
        if total_tokens + msg_tokens <= (max_tokens - reserved_completion):
            truncated.insert(0, msg)
            total_tokens += msg_tokens
        else:
            break

    return [system_msg] + truncated

# ---- main entry points -------------------------------------------------------
def ask_llm_hf(
    question: str,
    history_blocks: Union[str, List[Any]],
    doc_context: Union[str, List[str]] = "",
    user_id: Optional[int] = None
) -> str:
    """Non-streaming: must return a plain string."""
    if isinstance(doc_context, list):
        doc_context = "\n---\n".join(doc_context)
    if isinstance(history_blocks, list):
        history_blocks = format_history_blocks(history_blocks)

    # Lexical small-talk fast path (no docs required)
    if _is_smalltalk_text(question) and not (doc_context and doc_context.strip()):
        name = _extract_name(question) or _extract_name(history_blocks if isinstance(history_blocks, str) else "")
        if user_id and name:
            _save_memory(user_id, "user_name", f"User introduced as {name}")
        logging.info("🟢 Small-talk fast path (sync) triggered.")
        reply = _smalltalk_reply(question, name)
        return reply

    intent = classify_intent(question)

    # Small talk path (no docs needed)
    if intent in _SMALLTALK and not doc_context.strip():
        name = _extract_name(question) or _extract_name(history_blocks if isinstance(history_blocks, str) else "")
        if name:
            _save_memory(user_id, "user_name", f"User introduced as {name}")
        reply = _smalltalk_reply(question, name)
        return reply

    # Business question but NO context available
    if intent not in _SMALLTALK and not doc_context.strip():
        return "I don’t have that information yet. Which policy or document should I check?"

    logging.info(f"🧠 DOC CONTEXT PREVIEW:\n{doc_context[:500]}")

    # Create messages and trim if necessary
    msgs = make_chat_messages(history_blocks, question, doc_context, user_id)
    msgs = truncate_messages(msgs)
    msgs = enforce_alternating_roles(msgs)

    # Check correct role alternation
    expected_role = "user"
    for i, msg in enumerate(msgs[1:], start=1):  # skip system
        if msg["role"] != expected_role:
            logging.error(f"❌ Message {i} role invalid: expected {expected_role}, got {msg['role']}")
            return "Error: Invalid role sequence sent to LLM (must alternate user/assistant)"
        expected_role = "assistant" if expected_role == "user" else "user"

    logging.info(f"🧾 Final LLM Messages:\n{json.dumps(msgs, indent=2)}")

    system_prompt = msgs[0]["content"]
    doc_chunks = doc_context.split("\n---\n") if doc_context else []
    chat_history = msgs[1:]  # all trimmed messages except system
    chat_history = enforce_alternating_roles(chat_history)

    logging.info(f"📄 Document Chunks Preview:\n{doc_chunks[0][:500] if doc_chunks else 'None'}")

    # Send request to LLM
    try:
        answer = _chat_once(chat_history, doc_chunks, question, system_prompt)
    except Exception as e:
        logging.exception("❌ LLM call failed")
        return f"Error: {e}"

    # Handle incomplete answers
    if _is_incomplete(answer):
        logging.info("🔁 Detected incomplete answer. Sending 'Continue:'")
        chat_history.append({"role": "assistant", "content": answer})
        chat_history.append({"role": "user", "content": "Continue:"})
        try:
            continuation = _chat_once(chat_history, doc_chunks, "Continue:", system_prompt, max_tokens=120)
            answer += " " + continuation
        except Exception as e:
            logging.warning(f"⚠️ Continuation failed: {e}")

    logging.info(f"🤖 Final LLM Answer:\n{answer}")

    # Hallucination filtering (only when grounding applies)
    try:
        if should_reject_answer(answer, doc_context, intent):
            logging.warning("❌ Rejected answer due to low content match.")
            return "I don't know."
    except Exception as e:
        logging.error(f"⚠️ Hallucination check crashed: {e}")

    return answer.strip()

def ask_llm_hf_stream(
    question: str,
    history_blocks: Union[str, List[Any]],
    doc_context: Union[str, List[str]] = "",
    user_id: Optional[int] = None
) -> Generator[str, None, None]:
    """Streaming: must yield strings (tokens/chunks) and not return a plain string."""
    if isinstance(doc_context, list):
        doc_context = "\n---\n".join(doc_context)
    if isinstance(history_blocks, list):
        history_blocks = format_history_blocks(history_blocks)

    # Lexical small-talk fast path (stream)
    if _is_smalltalk_text(question) and not (doc_context and doc_context.strip()):
        name = _extract_name(question) or _extract_name(history_blocks if isinstance(history_blocks, str) else "")
        if user_id and name:
            _save_memory(user_id, "user_name", f"User introduced as {name}")
        logging.info("🟢 Small-talk fast path (stream) triggered.")
        reply = _smalltalk_reply(question, name)
        yield reply
        return

    intent = classify_intent(question)

    # Small talk path (stream)
    if intent in _SMALLTALK and not doc_context.strip():
        name = _extract_name(question) or _extract_name(history_blocks if isinstance(history_blocks, str) else "")
        if name:
            _save_memory(user_id, "user_name", f"User introduced as {name}")
        reply = _smalltalk_reply(question, name)
        yield reply
        return

    # Business question but NO context
    if intent not in _SMALLTALK and not doc_context.strip():
        yield "I don’t have that information yet. Which policy or document should I check?"
        return

    try:
        messages = make_chat_messages(history_blocks, question, doc_context, user_id)
        messages = truncate_messages(messages)

        system_prompt = messages[0]["content"]
        doc_chunks = doc_context.split("\n---\n") if doc_context else []
        chat_history = [msg for msg in messages if msg["role"] in ("user", "assistant")]

        for attempt in range(3):
            try:
                for token in _chat_stream(
                    chat_history=chat_history,
                    doc_chunks=doc_chunks,
                    user_query=question,
                    system_prompt=system_prompt
                ):
                    yield token
                return  # ✅ Success
            except Exception as e:
                logging.warning(f"⚠️ Stream attempt {attempt + 1} failed: {e}")
                time.sleep(2 * (attempt + 1))  # Exponential backoff

    except Exception as e:
        logging.error(f"❌ ask_llm_hf_stream failed: {e}")

    yield "I don't know."
