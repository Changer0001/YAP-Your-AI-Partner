import os, re, time, json, logging
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

VLLM_API_URL = os.getenv("VLLM_API_URL")
if not VLLM_API_URL:
    raise RuntimeError("VLLM_API_URL env var missing!")

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.3"

# ── Init ──────────────────────────────────────────────────────────────────────
logging.basicConfig(filename="app.log", filemode="a", level=logging.DEBUG)

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

def make_chat_messages(
    history_blocks: str, question: str, doc_context: str = ""
) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_INSTRUCTION}]

    if doc_context.strip():
        msgs[0]["content"] += (
            "\n\nUse ONLY the context below to answer. If the answer is not clearly found in this context, say: 'I don't know.'\n\n"
            "Context:\n" + doc_context.strip()
        )
    history_msgs = blocks_to_messages(history_blocks)

# Ensure alternating roles
    if history_msgs and history_msgs[-1]["role"] == "user":
        history_msgs.append({"role": "assistant", "content": "..."})  # or a placeholder

        # Then append the new user message
    history_msgs.append({
        "role": "user",
        "content": (
            f"{question.strip()}\n\n"
            "Important:\n"
            "1️⃣  Only answer if the information is clearly found in the context above or chat history; "
                "otherwise reply exactly with: I don't know.\n"
            "2️⃣  **Format the answer as a step-by-step list** (numbered or bulleted) whenever applicable."
        )
    })


    msgs.extend(history_msgs)

    logging.debug("📦 Final messages to LLM:\n%s", json.dumps(msgs, indent=2))

    return msgs[-30:]

# ── Core wrappers ─────────────────────────────────────────────────────────────
def _chat_once(messages, max_tokens=300, temperature=0.7):
    try:
        start = time.time()
        logging.debug("📦 Final messages to LLM (_chat_once):\n%s", json.dumps(messages, indent=2))
        response = requests.post(
            f"{VLLM_API_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }
        )
        response.raise_for_status()
        res = response.json()
        logging.info("⏱️ chat time %.2fs", time.time() - start)
        return res["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.exception("❌ chat_completion failed:")
        return f"Error: {e}"

def _chat_stream(messages, max_tokens=300, temperature=0.7):
    try:
        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }

        logging.debug("📦 Final messages to LLM (_chat_once):\n%s", json.dumps(messages, indent=2))

        response = requests.post(
            f"{VLLM_API_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload,
            stream=True
        )

        response.raise_for_status()

        for line in response.iter_lines():
            if not line or line == b"data: [DONE]":
                continue
            delta = line.decode("utf-8").removeprefix("data: ")
            content = json.loads(delta)["choices"][0]["delta"].get("content", "")
            yield content

    except requests.exceptions.HTTPError:
        logging.error("❌ HTTPError: %s", response.text)
        yield f"\n[ERROR] {response.text}"

    except Exception as e:
        logging.exception("❌ chat stream failed:")
        yield f"\n[ERROR] {e}"

# ── Public API ────────────────────────────────────────────────────────────────
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
            return
        except Exception as e:
            logging.warning(f"⚠️ Stream attempt {attempt + 1} failed: {e}")
            time.sleep(2 * (attempt + 1))

    yield "I don't know."
