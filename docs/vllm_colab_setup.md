
# 🧠 YAP LLM Backend Setup using vLLM + Colab + Ngrok

This document outlines the setup for running [Mistral-7B-Instruct-v0.3](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3) using `vLLM` in a Colab environment, with public exposure through `ngrok`.

---

## ✅ What We Achieved

- Deployed `vLLM` server inside Google Colab.
- Loaded **Mistral-7B-Instruct-v0.3** model.
- Connected to Hugging Face with a private access token.
- Exposed the server using `ngrok` to access it remotely.
- Successfully queried the `/v1/chat/completions` endpoint.

---

## 🧩 Requirements

- Google Colab Pro (preferably, for GPU access)
- A Hugging Face account with access to the gated Mistral repo.
- A Hugging Face **access token**.
- A free [Ngrok account](https://ngrok.com/) with your **auth token**.

---

## ⚙️ Step-by-Step Setup

### 🔹 1. Install dependencies

```python
!pip install --upgrade pip
!pip install vllm torch torchvision torchaudio xformers
!pip install "vllm[serve]" --upgrade
!pip install -q pyngrok
```

---

### 🔹 2. Authenticate Hugging Face

```python
from huggingface_hub import login
login("hf_your_token_here")
```

Or set it as environment variable:

```python
import os
os.environ["HUGGINGFACE_HUB_TOKEN"] = "hf_your_token_here"
```

---

### 🔹 3. Start the vLLM OpenAI-Compatible Server

```python
!nohup python3 -m vllm.entrypoints.openai.api_server \
  --model mistralai/Mistral-7B-Instruct-v0.3 \
  --tokenizer-mode mistral \
  --host 0.0.0.0 \
  --port 8000 > server.log 2>&1 &
```

> ✅ `nohup` makes the server run in background even when cell finishes.

Check logs:

```python
!tail -n 40 server.log
```

---

### 🔹 4. Set up Ngrok tunnel

```python
from pyngrok import ngrok

ngrok.set_auth_token("your-ngrok-auth-token")
public_url = ngrok.connect(8000)
print("🚀 Public vLLM endpoint:", public_url)
```

---

## 📡 Sample Request (via OpenAI-style endpoint)

```python
import requests

response = requests.post(
    "https://your-ngrok-url.ngrok-free.app/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    json={
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "messages": [
            {"role": "user", "content": "Who are you?"}
        ],
        "max_tokens": 100
    }
)

print(response.json())
```

**Expected Response**:
```json
{
  "id": "...",
  "object": "chat.completion",
  "model": "mistralai/Mistral-7B-Instruct-v0.3",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "I am a model of artificial intelligence..."
      },
      ...
    }
  ]
}
```

---

## 📌 Notes

- 🔁 Each time you restart Colab, you’ll get a new ngrok URL.
- 🔐 Always authenticate to Hugging Face before launching the server.
- 🚫 If `ConnectionRefusedError` appears, check if the server is actually running.
