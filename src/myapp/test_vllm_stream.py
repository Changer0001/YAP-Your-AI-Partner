import os
import json
import logging
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
VLLM_API_URL = os.getenv("VLLM_API_URL")

if not VLLM_API_URL:
    raise RuntimeError("❌ VLLM_API_URL not set in .env file")

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.3"

logging.basicConfig(level=logging.INFO)

# Sample chat message to send
payload = {
    "model": MODEL_NAME,
    "messages": [
        {"role": "user", "content": "Hello! Can you explain what YAP does?"}
    ],
    "max_tokens": 300,
    "temperature": 0.7,
    "stream": False
}

def test_vllm_completion():
    try:
        logging.info(f"🌐 Sending request to {VLLM_API_URL}/v1/chat/completions")
        response = requests.post(
            f"{VLLM_API_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        response.raise_for_status()
        data = response.json()

        print("\n✅ Response from vLLM:")
        print(json.dumps(data, indent=2))

        assistant_reply = data["choices"][0]["message"]["content"]
        print("\n🤖 Assistant says:")
        print(assistant_reply.strip())

    except Exception as e:
        logging.exception("❌ Error while sending request to vLLM")

if __name__ == "__main__":
    test_vllm_completion()
