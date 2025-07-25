
import requests, time, logging, json
import os
from dotenv import load_dotenv
from myapp.token_utils import trim_messages_by_tokens, trim_chunks_by_tokens,count_tokens

load_dotenv()

VLLM_API_URL = os.getenv("VLLM_API_URL")
if not VLLM_API_URL:
    raise RuntimeError("VLLM_API_URL environment variable is missing!")

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.3"

def _chat_once(chat_history, doc_chunks, user_query, system_prompt, max_tokens=300, temperature=0.7):
    try:
        messages = build_safe_messages(system_prompt, chat_history, doc_chunks, user_query)

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


def _chat_stream(chat_history, doc_chunks, user_query, system_prompt, max_tokens=300, temperature=0.7):
    try:
        messages = build_safe_messages(system_prompt, chat_history, doc_chunks, user_query)

        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }

        logging.debug("📦 Final messages to LLM (_chat_stream):\n%s", json.dumps(messages, indent=2))

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



def build_safe_messages(system_prompt: str, chat_history: list, doc_chunks: list, user_query: str) -> list:
    MAX_TOKENS = 4096
    RESERVED_FOR_COMPLETION = 400

    system_tokens = count_tokens(system_prompt)
    available_tokens = MAX_TOKENS - RESERVED_FOR_COMPLETION - system_tokens

    # Split available budget between chat and docs
    chat_token_budget = int(available_tokens * 0.6)
    doc_token_budget = available_tokens - chat_token_budget

    trimmed_chat = trim_messages_by_tokens(chat_history, max_tokens=chat_token_budget)
    trimmed_docs = trim_chunks_by_tokens(doc_chunks, max_tokens=doc_token_budget)

    # Compose document context
    doc_context = "\n\n".join(trimmed_docs)

    messages = [{"role": "system", "content": system_prompt}]
    if doc_context:
        messages.append({"role": "system", "content": f"Context:\n{doc_context}"})
    messages += trimmed_chat
    messages.append({"role": "user", "content": user_query})

    return messages