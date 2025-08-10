# llm_core.py
import os
import json
import logging
import requests
from dotenv import load_dotenv
from app.core.token_utils import (
    trim_messages_by_tokens,
    trim_chunks_by_tokens,
    count_tokens
)

load_dotenv()
VLLM_API_URL = os.getenv("VLLM_API_URL")
if not VLLM_API_URL:
    raise RuntimeError("VLLM_API_URL environment variable is missing!")

MODEL_NAME = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-14B-Instruct")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "32768"))
RESERVED_COMPLETION = int(os.getenv("RESERVED_COMPLETION", "1536"))
RESERVED_HEADROOM = int(os.getenv("RESERVED_HEADROOM", "300"))


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
    assert isinstance(system_prompt, str)
    assert isinstance(user_query, str)
    assert isinstance(doc_chunks, list)

    # Calculate base system tokens before adding context
    base_tokens = count_tokens(system_prompt)
    buffer = 100 + len(chat_history) * 4

    # Figure out total tokens we can afford for docs
    total_budget = MAX_TOKENS - RESERVED_COMPLETION - base_tokens - count_tokens(user_query) - buffer
    doc_budget = max(int(total_budget * 0.4), 0)  # you can tune this ratio

    # Trim doc chunks to fit in doc_budget
    doc_text = ""
    if doc_chunks:
        combined = []
        for chunk in doc_chunks:
            combined.append(chunk)
            current_text = "\n---\n".join(combined)
            if count_tokens(current_text) > doc_budget:
                combined.pop()  # remove last that overflowed
                break
        doc_text = "\n---\n".join(combined)

    # Append context safely
    if doc_text:
        system_prompt += "\n\nContext:\n" + doc_text

    # Check system + query tokens again
    system_tokens = count_tokens(system_prompt)
    query_tokens = count_tokens(user_query)
    remaining = MAX_TOKENS - RESERVED_COMPLETION - system_tokens - query_tokens - buffer

    # Trim query if needed
    if remaining < 0:
        max_query_tokens = MAX_TOKENS - RESERVED_COMPLETION - system_tokens - buffer
        while count_tokens(user_query) > max_query_tokens and len(user_query) > 10:
            user_query = user_query[:-50]

    # Allocate remaining tokens
    chat_budget = max(MAX_TOKENS - RESERVED_COMPLETION - system_tokens - count_tokens(user_query), 0)
    trimmed_chat = trim_messages_by_tokens(chat_history, chat_budget)

    # Build final message sequence
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(trimmed_chat)
    messages.append({"role": "user", "content": user_query})

    return enforce_alternating_roles(messages)



def _chat_once(chat_history, doc_chunks, user_query, system_prompt, max_tokens=300, temperature=0.7):
    try:
        messages = build_safe_messages(system_prompt, chat_history, doc_chunks, user_query)
        allowed_tokens = MAX_TOKENS - max_tokens
        trimmed_messages = trim_messages_by_tokens(messages, allowed_tokens)

        response = requests.post(
            f"{VLLM_API_URL}/v1/chat/completions",  # ✅ FIXED PATH
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
        logging.exception("❌ chat_once failed:")
        return f"Error: {e}"

def _chat_stream(chat_history, doc_chunks, user_query, system_prompt, max_tokens=300, temperature=0.7):
    try:
        messages = build_safe_messages(system_prompt, chat_history, doc_chunks, user_query)
        allowed_tokens = MAX_TOKENS - max_tokens
        trimmed_messages = trim_messages_by_tokens(messages, allowed_tokens)

        response = requests.post(
            f"{VLLM_API_URL}/v1/chat/completions",  # ✅ FIXED PATH
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
            try:
                payload = json.loads(line.decode("utf-8").removeprefix("data: "))
                yield payload["choices"][0]["delta"].get("content", "")
            except Exception as e:
                logging.warning(f"⚠️ Failed to parse stream: {e}")
    except requests.exceptions.HTTPError:
        logging.error("❌ HTTPError: %s", response.text)
        yield f"[ERROR] {response.text}"
    except Exception as e:
        logging.exception("❌ chat_stream failed:")
        yield f"[ERROR] {e}"
