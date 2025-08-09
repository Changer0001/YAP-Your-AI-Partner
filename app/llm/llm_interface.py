#llm_interface.py
import os, re, time, json, logging
from typing import List, Dict, Any, Union
from dotenv import load_dotenv
from app.db.memory_store import Memory
from app.db.database import SessionLocal
from app.llm.llm_core import _chat_once, _chat_stream, enforce_alternating_roles
from app.core.token_utils import count_tokens

load_dotenv()

VLLM_API_URL = os.getenv("VLLM_API_URL")
if not VLLM_API_URL:
    raise RuntimeError("VLLM_API_URL env var missing!")

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.3"

logging.basicConfig(filename="app.log", filemode="a", level=logging.DEBUG)

SYSTEM_INSTRUCTION = (
    "You are a helpful assistant. Use the conversation history and document context to answer questions as accurately as possible. "
    "If the answer is not clearly available in the history or documents, it's okay to say 'I don't know' or clarify that the information is missing. "
    "Avoid making up facts or hallucinating."
)


_INCOMPLETE_RE = re.compile(r"\b(and|but|or|so|because)$", re.IGNORECASE)

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
            role = "user"
            content = line[5:].strip()
        elif line.startswith("🤖 A:"):
            role = "assistant"
            content = line[5:].strip()
            if content.startswith("[ERROR]"):
                continue
        else:
            continue
        if role == last_role:
            continue
        msgs.append({"role": role, "content": content})
        last_role = role
    return msgs

def make_chat_messages(history_blocks: str, question: str, doc_context: str = "", user_id: int = None) -> List[Dict[str, str]]:
    system_content = SYSTEM_INSTRUCTION

    if doc_context.strip():
        system_content += (
            "\n\nUse ONLY the context below to answer. If the answer is not clearly and directly found in the context below, say: 'I don't know.' Do NOT guess or speculate.\n\n"
            "Context:\n" + doc_context.strip()
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

def truncate_messages(messages, max_tokens=4096, reserved_completion=300):
    if not messages or len(messages) < 2:
        return messages

    system_msg = messages[0]
    rest = messages[1:]
    total_tokens = count_tokens(system_msg["content"])
    truncated = []

    # Reverse through messages, skipping system
    for msg in reversed(rest):
        msg_tokens = count_tokens(msg["content"])
        if total_tokens + msg_tokens <= (max_tokens - reserved_completion):
            truncated.insert(0, msg)
            total_tokens += msg_tokens
        else:
            break

    return [system_msg] + truncated



def ask_llm_hf(
    question: str,
    history_blocks: Union[str, List[Any]],
    doc_context: Union[str, List[str]] = "",
    user_id: int = None
) -> str:
    if isinstance(doc_context, list):
        doc_context = "\n---\n".join(doc_context)
    if isinstance(history_blocks, list):
        history_blocks = format_history_blocks(history_blocks)

    logging.info(f"🧠 DOC CONTEXT PREVIEW:\n{doc_context[:500]}")

    # Create messages and trim if necessary
    msgs = make_chat_messages(history_blocks, question, doc_context, user_id)
    msgs = truncate_messages(msgs, max_tokens=4096, reserved_completion=300)
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

    # Filter unrelated math fragments
    if "let l =" in answer.lower() or "which is the" in answer.lower():
        logging.warning("🧹 Cleaning unrelated math/question garbage.")
        answer = answer.split("Answer:")[-1].strip()

    # Hallucination filtering
    try:
        if should_reject_answer(answer, doc_context):
            logging.warning("❌ Rejected answer due to low content match.")
            return "I don't know."
    except Exception as e:
        logging.error(f"⚠️ Hallucination check crashed: {e}")

    return answer.strip()

def should_reject_answer(answer: str, doc_context: str) -> bool:
    if not answer.strip():
        return True

    context_words = set(doc_context.lower().split())
    answer_words = set(answer.lower().split())

    overlap = len(context_words & answer_words)
    total = max(len(answer_words), 1)

    match_ratio = overlap / total

    # Stricter rejection: must match at least 3% of answer words
    if match_ratio < 0.03:
        logging.warning(f"🚫 Rejected answer due to low overlap: {match_ratio:.2%}")
        return True

    # Special case: look for numeric mismatch in days
    if "day" in answer.lower() and "14" not in answer and "14" in doc_context:
        logging.warning("🚫 Rejected answer due to mismatch in refund days.")
        return True

    return False




def ask_llm_hf_stream(
    question: str,
    history_blocks: Union[str, List[Any]],
    doc_context: Union[str, List[str]] = "",
    user_id: int = None
):
    if isinstance(doc_context, list):
        doc_context = "\n---\n".join(doc_context)
    if isinstance(history_blocks, list):
        history_blocks = format_history_blocks(history_blocks)

    if not doc_context.strip() and not history_blocks:
        yield "I don't know."
        return

    try:
        messages = make_chat_messages(history_blocks, question, doc_context, user_id)
        messages = truncate_messages(messages, max_tokens=4096, reserved_completion=300)

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

