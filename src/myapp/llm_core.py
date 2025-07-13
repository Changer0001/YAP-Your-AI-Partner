
import requests, time, logging, json
import os
from dotenv import load_dotenv

load_dotenv()

VLLM_API_URL = os.getenv("VLLM_API_URL")
if not VLLM_API_URL:
    raise RuntimeError("VLLM_API_URL environment variable is missing!")

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.3"

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