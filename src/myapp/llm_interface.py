import os
import re
import time
import logging
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# ── 0. Init ────────────────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(filename="app.log", filemode="a", level=logging.DEBUG)

HF_API_TOKEN = os.getenv("HF_API_TOKEN")
client = InferenceClient(
    model="mistralai/Mistral-7B-Instruct-v0.2",
    token=HF_API_TOKEN
)

SYSTEM_INSTRUCTION = (
    "You are a helpful assistant. Use the conversation history and the provided "
    "document context to answer follow-up questions. Answer ONLY from that "
    "information. If the answer is not there, reply with: I don't know."
)

# ── 1. Prompt assembly helpers ────────────────────────────────────────────────
def build_chat_messages(history: str, question: str, doc_context: str = "") -> list:
    """
    Convert history + document context into OpenAI-style chat messages.
    """
    messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]

    # Inject retrieved docs (if any) as assistant context
    if doc_context.strip():
        messages.append(
            {"role": "assistant", "content": f"Context:\n{doc_context.strip()}"}
        )

    # Re-add the last few Q/A pairs (already formatted by chat_store)
    for block in history.strip().split("\n\n"):
        if block.startswith("🧑 Q:") and "🤖 A:" in block:
            try:
                q, a = block.split("🤖 A:")
                messages.append({"role": "user", "content": q.replace("🧑 Q:", "").strip()})
                messages.append({"role": "assistant", "content": a.strip()})
            except ValueError:
                continue                        # ignore malformed block

    messages.append({"role": "user", "content": question})
    return messages


# ── 2. Synchronous completion ────────────────────────────────────────────────
def ask_llm_hf(question: str,
               history_context: str,
               doc_context: str = "",
               max_tokens: int = 300,
               temperature: float = 0.7) -> str:
    """
    Blocking call — returns full answer string.
    """
    try:
        messages   = build_chat_messages(history_context, question, doc_context)
        start_time = time.time()

        # ─ Debug: dump prompt head (optional) ─
        logging.debug("🧪 Prompt head:\n%s", "\n".join(
            f"[{m['role'].upper()}] {m['content'][:160].replace(chr(10), ' ')}"
            for m in messages[:4]
        ))

        result  = client.chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        elapsed = time.time() - start_time
        logging.info("⏱️ Answer generated in %.2fs", elapsed)

        return result.choices[0].message.content.strip()

    except Exception as e:
        logging.exception("❌ Generation failed:")
        return f"❌ Error: {e}"


# ── 3. Streaming completion ──────────────────────────────────────────────────
def ask_llm_hf_stream(question: str,
                      history_context: str,
                      doc_context: str = "",
                      max_tokens: int = 300,
                      temperature: float = 0.7):
    """
    Generator that yields partial tokens.
    """
    try:
        messages = build_chat_messages(history_context, question, doc_context)
        stream   = client.chat_completion(
            messages=messages,
            stream=True,
            max_tokens=max_tokens,
            temperature=temperature
        )

        for chunk in stream:
            if chunk.choices and "content" in chunk.choices[0].delta:
                yield chunk.choices[0].delta["content"]

    except StopIteration:
        yield "[ERROR] Streaming not supported for this model."

    except Exception as e:
        logging.exception("❌ Streaming failed:")
        yield f"\n[ERROR] {e}"


# ── 4. Post-filter helpers ───────────────────────────────────────────────────
_INCOMPLETE_RE = re.compile(r"\b(and|but|or|so|because)$", re.IGNORECASE)

def _is_incomplete(text: str) -> bool:
    text = text.strip()
    if not text:
        return True
    if text[-1] not in ".!?":
        return True
    if text.endswith("...") or _INCOMPLETE_RE.search(text):
        return True
    return False


def get_complete_answer(question: str,
                        history_context: str,
                        doc_context: str = "",
                        max_tries: int = 2) -> str:
    """
    Simple retry loop if the model cuts off mid-sentence.
    """
    answer = ask_llm_hf(question, history_context, doc_context)
    tries  = 1

    while _is_incomplete(answer) and tries < max_tries:
        logging.info("🔄 Regenerating continuation (try %d)…", tries + 1)
        followup = f"{answer.strip()}\n\nContinue:"
        try:
            continuation = client.chat_completion(
                messages=[{"role": "user", "content": followup}],
                max_tokens=120,
                temperature=0.7
            )
            answer += " " + continuation.choices[0].message.content.strip()
        except Exception as e:
            logging.exception("❌ Error during continuation:")
            break
        tries += 1

    return answer.strip()
