# 🛠️ YAP Token Overflow & Retrieval Debug Log

This document outlines the steps taken to resolve token overflow and retrieval issues encountered in the YAP app using a FastAPI + vLLM backend and ChromaDB-based RAG.

---

## 🧩 Problem Summary

- ❌ Certain user queries like "How to add user on Sertifi" or "EMC access steps" failed with:
  ```
  ValueError: System message alone exceeds token limit.
  ```
- ✅ Simpler or test queries (e.g., "hello", "what services YAP offers") worked fine.
- 🔍 Retrieval logs showed context was correctly pulled from ChromaDB, but the combined prompt (system + docs + chat + query) exceeded 4096 tokens.

---

## 🧪 Debugging & Fixes

### ✅ Step 1: Verified Context Fetching from ChromaDB

- Logged retrieved chunks and distances.
- Validated that relevant chunks were returned for both “sertifi” and “emc” queries.

### ✅ Step 2: Identified Overflow Origin

- Issue was raised from `build_safe_messages()`.
- Overflow occurred due to adding `doc_chunks` into the `system_prompt` **before** trimming tokens.

### ✅ Step 3: Rewrote `build_safe_messages()`

- Moved `doc_chunks` token trimming **before** system prompt extension.
- Implemented controlled token budget allocation:
  - `40%` for document context.
  - `60%` for chat history.
- Applied fallback trimming on:
  - `doc_chunks` by max budget.
  - `chat_history` by `trim_messages_by_tokens()`.
  - `user_query` if necessary.

### ✅ Step 4: Re-tested Long Queries

- Verified both long questions now respond with accurate, chunk-based answers:
  - `"how to add user on sertifi"`
  - `"how to add user on emc"`

### ✅ Step 5: PowerShell Script Testing

- Used PowerShell with `Invoke-RestMethod` to validate token-authenticated `/ask` endpoint with test questions.

---

## ✅ Outcome

YAP can now safely process document-heavy queries without exceeding the model’s token limit, and returns grounded, complete responses.

> **Total Context Used:** Document + Query + Chat + System Prompt = ✅ Within 4096 tokens.

---

## 🔧 Files Updated

- `llm_core.py` → `build_safe_messages()` rewritten
- `token_utils.py` → Confirmed trimming functions working
- Logging added to ensure retrieved documents and messages are traceable

---

## 📌 Recommendation

Keep logs of token usage, especially for:
- System prompt growth
- Chunk count vs size
- Chat history accumulation

Monitor with `count_tokens()` and adjust budgets dynamically for optimal performance.