# YAP — Model Upgrade & Backend Notes (Aug 2025)

> This doc captures the changes we made migrating YAP from **Mistral-7B-Instruct** to **Qwen/Qwen2.5-14B-Instruct (native 32k)**, stabilizing vLLM, improving retrieval and streaming, and tightening the app behavior. Save as `docs/YAP_MODEL_MIGRATION.md`.

---

## 1) Why we changed

- Needed **larger context** (32k), **higher accuracy**, and **fast, private** local inference on a **single GPU**.
- Switched from `mistralai/Mistral-7B-Instruct-v0.3` → `Qwen/Qwen2.5-14B-Instruct` (native 32k).
- vLLM used as a **self-hosted OpenAI-compatible API** behind ngrok.

---

## 2) Runtime & vLLM

### Final (working) vLLM launch (single 40 GB GPU)

```bash
# free port/process (optional)
fuser -k 8000/tcp || true
kill -9 $(pgrep -f "vllm.entrypoints.openai.api_server") 2>/dev/null || true

# fragmentation hint (helps with big inits)
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# start vLLM (32k native)
nohup python3 -m vllm.entrypoints.openai.api_server   --model Qwen/Qwen2.5-14B-Instruct   --host 127.0.0.1 --port 8000   --dtype float16   --max-model-len 32768   --gpu-memory-utilization 0.95   > server.log 2>&1 &
```

**Notes**
- We tried `--kv-cache-dtype fp8` and `--quantization awq`.  
  - **AWQ** loaded but added scheduler/engine constraints and could be slower; we reverted to **FP16 weights** for stability/perf.  
  - **FP8 KV cache** reduced memory, but with the current engine toggled us to v0-path and added accuracy tradeoffs. We kept **default KV** to keep outputs stable.
- OOM/“No available memory for cache blocks” fixes:
  - Lower `--max-model-len` or raise `--gpu-memory-utilization`.
  - Make sure no other CUDA processes are using VRAM.
  - Keep `expandable_segments:True`.

### Tailing logs

```bash
tail -n 80 server.log
```

---

## 3) Environment

### `.env` (template)

```
# vLLM
VLLM_API_URL=https://<your-current-ngrok-subdomain>.ngrok-free.app
VLLM_MODEL=Qwen/Qwen2.5-14B-Instruct
MAX_TOKENS=32768
RESERVED_COMPLETION=1536
RESERVED_HEADROOM=300

# App
OPENAI_API_KEY=sk-...             # if used elsewhere
HF_API_TOKEN=hf_...               # if used elsewhere
SECRET_KEY=<random>
COOKIE_PASSWORD=<random>
GOOGLE_PLACES_API_KEY=<optional>
RUNNING_IN_COLAB=false
```

> **Important:** Update `VLLM_API_URL` every time ngrok gives you a new subdomain. The “offline endpoint” 404s were from pointing at an old ngrok URL.

---

## 4) Code changes (high level)

### 4.1 `app/llm/llm_core.py`
- Reads **model & token limits from env**.
- Safe message building with **token budgeting**:
  - Allocates ~40% of space for docs, trims chat history to fit (`trim_messages_by_tokens`, `count_tokens`).
- Uses vLLM **OpenAI `/v1/chat/completions`** endpoint.
- Streaming and non-streaming paths kept separate and type-clean.

### 4.2 `app/llm/llm_interface.py` (major polish)
- Added **small-talk fast path** that doesn’t require RAG:
  - Recognizes “hi/hello/thanks/bye” even with no docs.
  - Extracts simple names from phrases like “Hi, I’m Burak” and stores in memory.
- Preserves **grounded answers** for policy/business queries:
  - If no context and it’s not small talk → “I don’t have that information yet…”.
  - **Hallucination guard**: low overlap with context → return “I don’t know.”
- Clean **return types**:
  - `ask_llm_hf` returns **string**.
  - `ask_llm_hf_stream` **yields** strings (no bare returns).
- Logs tuned for clarity.

### 4.3 `app/retriever/retriever.py`
- Uses ChromaDB collection + sentence embedding.
- **Dynamic thresholding** via `get_dynamic_threshold(query)`.
- **Query boosting** (e.g., “refund” → adds synonyms).
- **Score adjustments** by metadata (position/heading).
- Robust filtering of short/empty chunks.

### 4.4 `app/api/api_routes.py`
- Typed `AskRequest.history` entries.
- `/ask` (blocking) & `/ask/stream` (SSE) stable:
  - `StreamingResponse` with a **plain generator** that yields `data:` JSON lines.
  - Saves full answer on completion.
- Uses `allocate_token_budget` to fit history/docs before LLM call.

### 4.5 Intent classification (`app/retriever/intent_classifier.py`)
- Embedding-based few-shot “greeting/goodbye/thank_you/refund_query/unknown”.
- Threshold default 0.85; can tune later.

---

## 5) Git & ignore

### `.gitignore` (high value parts)
- Ignore **venv** folders, OS cruft, logs, caches, ChromaDB store, model/tokenizer assets, large checkpoints.
- Keep empty directories with `.gitkeep` where needed.

### Example commit history
```bash
git add .
git commit -m "YAP: migrate to Qwen2.5-14B (32k), add small-talk path, stable streaming, safer RAG + token budgeting"
git push origin YAP-v1
```

---

## 6) Known issues & fixes

- **Ngrok offline (ERR_NGROK_3200)** → update `VLLM_API_URL` to the **current** tunnel.
- **CUDA OOM / KV cache too small** → lower `--max-model-len`, increase `--gpu-memory-utilization`, or drop fp8 kv/quant for stability.
- **Chroma returns nothing** → ensure docs are actually ingested; dynamic threshold may skip weak matches by design.
- **Pylance “generator type” error** → fixed by making `ask_llm_hf` return string only; `ask_llm_hf_stream` yield tokens only.

---

## 7) How it works at a glance

```
User → /ask or /ask/stream
  ├─ get_recent_history(user_id)
  ├─ retrieve(query)  # Chroma + boosts + dynamic threshold
  ├─ allocate_token_budget(...)
  ├─ ask_llm_hf(_stream)(...) → llm_core → vLLM → Qwen2.5-14B
  └─ save_chat_history(user_id, question, answer)
```

**Small talk path**
- If the query looks like greeting/thanks/etc. → respond immediately (no docs), optionally store “user_name” memory.

**Grounded QA**
- If it’s a business/policy question:
  - If **no docs** → ask which policy/doc to check.
  - If **docs found** → answer strictly from context; otherwise say “I don’t know.”

---

## 8) Commands you’ll reuse

### Start backend (FastAPI/Uvicorn)
```bash
# from project root
uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

### Start vLLM (see Section 2)
```bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
nohup python3 -m vllm.entrypoints.openai.api_server   --model Qwen/Qwen2.5-14B-Instruct   --host 127.0.0.1 --port 8000   --dtype float16   --max-model-len 32768   --gpu-memory-utilization 0.95   > server.log 2>&1 &
```

### Expose via ngrok
```python
from pyngrok import ngrok
ngrok.set_auth_token("<your-ngrok-token>")
public_url = ngrok.connect(8000)
print("Public VLLM URL:", public_url)  # put this into .env as VLLM_API_URL
```

---

## 9) Security & privacy posture (current status)

- **Self-hosted inference** (no vendor logs if you keep it on your infra).
- **No customer data** sent to 3rd-party LLMs when using vLLM locally.
- Memory store only keeps lightweight session facts (e.g., “user name = Burak”).
- API endpoints protected by **token auth**; add rate-limits before voice/phone rollout.

---

## 10) Next steps

- **Voice/phone pipeline:** ASR → YAP → TTS, with turn-by-turn state (appointments, bookings).
- **Tooling**: Add function calling for booking APIs (Stripe, Calendly, PoS, etc.).
- **Guardrails**: Per-tenant content allowlists; PII redaction in logs.
- **Eval harness**: regression tests for refund/booking flows.
- **Model variants**: try **Qwen2.5-7B-Instruct** for cost, or **14B-AWQ** once vLLM AWQ path stabilizes for your setup.

---

## 11) Quick checklist (done ✅)

- ✅ Switched model to `Qwen/Qwen2.5-14B-Instruct` (32k native).  
- ✅ vLLM server stable on single 40 GB GPU with FP16.  
- ✅ `.env` unified; model/token limits pulled from env.  
- ✅ Small-talk path + name capture + memory save.  
- ✅ “Grounded-only” business answers; “I don’t know” fallback.  
- ✅ Streaming endpoint stable (`StreamingResponse` with SSE).  
- ✅ Retriever tuned with dynamic threshold + query/score boosts.  
- ✅ `.gitignore` excludes venv, sqlite/vector stores, models, large artifacts.  
- ✅ Pylance type warnings resolved.

---

## 12) How to save this file

```bash
mkdir -p docs
# save this content as docs/YAP_MODEL_MIGRATION.md
git add docs/YAP_MODEL_MIGRATION.md
git commit -m "docs: capture YAP model migration & backend changes (Aug 2025)"
git push origin YAP-v1
```
