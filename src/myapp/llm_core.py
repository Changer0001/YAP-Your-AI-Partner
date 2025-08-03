import os
import time
import json
import logging
import requests
from dotenv import load_dotenv
from myapp.token_utils import (
    trim_messages_by_tokens,
    trim_chunks_by_tokens,
    count_tokens
)

# ── Config ─────────────────────────────────────────────────────
load_dotenv()

VLLM_API_URL = os.getenv("VLLM_API_URL")
if not VLLM_API_URL:
    raise RuntimeError("VLLM_API_URL environment variable is missing!")

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.3"
MAX_TOKENS = 4096
RESERVED_COMPLETION = 300

# ── Utils ──────────────────────────────────────────────────────
def enforce_alternating_roles(messages: list) -> list:
    result = []
    last_role = None
    for msg in messages:
        if msg["role"] == last_role and msg["role"] != "system":
            continue
        result.append(msg)
        last_role = msg["role"]
    return result

def build_safe_messages(system_prompt, chat_history, doc_chunks, user_query):
    system_tokens = count_tokens(system_prompt)
    user_query_tokens = count_tokens(user_query)
    template_buffer = len(chat_history) * 4 + 100

    available_tokens = MAX_TOKENS - RESERVED_COMPLETION - system_tokens - user_query_tokens - template_buffer

    if available_tokens < 0:
        max_query_tokens = MAX_TOKENS - RESERVED_COMPLETION - system_tokens - template_buffer
        trimmed_query = user_query
        while count_tokens(trimmed_query) > max_query_tokens:
            trimmed_query = trimmed_query[:-50]  # Trim 50 chars at a time
        user_query = trimmed_query
        user_query_tokens = count_tokens(user_query)
        available_tokens = MAX_TOKENS - RESERVED_COMPLETION - system_tokens - user_query_tokens - template_buffer

    chat_budget = int(available_tokens * 0.6)
    doc_budget = available_tokens - chat_budget

    trimmed_chat = trim_messages_by_tokens(chat_history, chat_budget, reserved_completion=0)
    trimmed_docs = trim_chunks_by_tokens(doc_chunks, doc_budget)

    doc_context = "\n\n".join(trimmed_docs)
    full_system_prompt = system_prompt
    if doc_context:
        full_system_prompt += "\n\nContext:\n" + doc_context

    messages = [
        {"role": "system", "content": full_system_prompt},
        *trimmed_chat,
        {"role": "user", "content": user_query}
    ]
    return enforce_alternating_roles(messages)


# ── Inference (non-streaming) ─────────────────────────────────
def _chat_once(chat_history, doc_chunks, user_query, system_prompt, max_tokens=300, temperature=0.7):
    try:
        messages = build_safe_messages(system_prompt, chat_history, doc_chunks, user_query)

        allowed_tokens = MAX_TOKENS - max_tokens
        trimmed_messages = trim_messages_by_tokens(messages, allowed_tokens, reserved_completion=0)

        final_total = sum(count_tokens(m["content"]) for m in trimmed_messages)
        if final_total + max_tokens > MAX_TOKENS:
            logging.warning("⚠️ Final token count too high. Hard trimming applied.")
            trimmed_messages = trim_messages_by_tokens(trimmed_messages, MAX_TOKENS - max_tokens, reserved_completion=0)

        total = sum(count_tokens(m["content"]) for m in trimmed_messages)
        logging.debug(f"🔢 Final token count (actual sent): messages={total}, completion={max_tokens}, total={total + max_tokens}")

        response = requests.post(
            f"{VLLM_API_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": MODEL_NAME,
                "messages": trimmed_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logging.exception("❌ chat_completion failed:")
        return f"Error: {e}"

# ── Inference (streaming) ─────────────────────────────────────
def _chat_stream(chat_history, doc_chunks, user_query, system_prompt, max_tokens=300, temperature=0.7):
    try:
        messages = build_safe_messages(system_prompt, chat_history, doc_chunks, user_query)

        allowed_tokens = MAX_TOKENS - max_tokens
        trimmed_messages = trim_messages_by_tokens(messages, allowed_tokens, reserved_completion=0)

        final_total = sum(count_tokens(m["content"]) for m in trimmed_messages)
        if final_total + max_tokens > MAX_TOKENS:
            logging.warning("⚠️ Final token count too high. Hard trimming applied.")
            trimmed_messages = trim_messages_by_tokens(trimmed_messages, MAX_TOKENS - max_tokens, reserved_completion=0)

        total = sum(count_tokens(m["content"]) for m in trimmed_messages)
        logging.debug(f"🔢 Final token count (actual sent - stream): messages={total}, completion={max_tokens}, total={total + max_tokens}")

        response = requests.post(
            f"{VLLM_API_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": MODEL_NAME,
                "messages": trimmed_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True
            },
            stream=True
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if not line or line == b"data: [DONE]":
                continue

            delta = line.decode("utf-8").removeprefix("data: ")
            print(f"🧪 Raw stream delta:\n{delta}")

            try:
                data = json.loads(delta)

                # Handle OpenAI-style response
                if isinstance(data, dict) and "choices" in data:
                    content_piece = data["choices"][0].get("delta", {}).get("content", "")
                # Handle raw string wrapped in list or as string (not JSON-structured)
                elif isinstance(data, list) and isinstance(data[0], str):
                    content_piece = data[0]
                elif isinstance(data, str):
                    content_piece = data
                else:
                    content_piece = ""
            except Exception as e:
                logging.warning(f"⚠️ Failed to parse stream chunk: {e} | Raw: {delta}")
                continue

            if content_piece:
                print(f"🔹 Stream Content Piece: {content_piece}")
                yield content_piece


    except requests.exceptions.HTTPError:
        logging.error("❌ HTTPError: %s", response.text)
        yield f"\n[ERROR] {response.text}"
    except Exception as e:
        logging.exception("❌ chat stream failed:")
        yield f"\n[ERROR] {e}"
