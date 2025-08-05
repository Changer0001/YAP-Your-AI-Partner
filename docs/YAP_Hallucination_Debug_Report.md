# 🐛 YAP Hallucination Debug Report

**Date:** 2025-08-05

## 📌 Problem Summary

YAP is hallucinating in the **real application flow**, but **not hallucinating in the test file**. This discrepancy indicates differences in how context, documents, or prompts are handled between the two environments.

---

## ⚠️ Identified Issues & Fixes

### 1. ❌ Real Documents Not Retrieved
- **Symptom:** `WARNING: Skipping doc X due to high distance`
- **Cause:** Document similarity score too high (irrelevant)
- **Fix:** 
  - Reduce similarity threshold
  - Improve embeddings or chunking
  - Log what is returned from retriever:

```python
logger.info(f"📄 Retrieved {len(docs)} docs: {[doc.metadata for doc in docs]}")
```

---

### 2. 📉 Poor Quality or Incomplete Chunks
- **Symptom:** Output contains vague or generic text
- **Cause:** Chunks are broken mid-sentence or not useful
- **Fix:**
  - Improve chunking logic (`chunk_text()`)
  - Use metadata-aware chunking (e.g., section headers, filenames)

---

### 3. 🧠 Token Limit Exceeded (4096 for Mistral)
- **Symptom:** Output ignores context or behaves like generic chatbot
- **Cause:** Combined token count of history + context + question > 4096
- **Fix:** 
  - Trim history and/or context
  - Log total tokens before sending:

```python
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-Instruct-v0.3")
total_tokens = sum(len(tokenizer.encode(m["content"])) for m in messages)
logger.info(f"🔢 Total tokens before generation: {total_tokens}")
```

---

### 4. 🤖 Hallucination Filtering Disabled
- **Symptom:** Assistant invents content not in the documents
- **Cause:** `enforce_context_only=False` or missing rejection logic
- **Fix:**
  - Enable rejection in `ask_llm_hf` or `ask_llm_hf_stream`:
```python
enforce_context_only=True
reject_if_no_context_match=True
```

---

### 5. 💬 Inconsistent Prompt or Message Formatting
- **Symptom:** Different behavior between test and real
- **Cause:** System prompt or messages differ
- **Fix:** Use strict prompt in both:
```python
system_prompt = """
You are a helpful assistant. Only answer if the answer exists in the provided context or chat history.
If not, say "I don't know." Do not make up information.
"""
```

---

### 6. 🧪 Test File Has Hardcoded Filters
- **Symptom:** Test works fine due to stricter logic
- **Cause:** Real app doesn't reuse test logic
- **Fix:** Extract shared logic into a common utility (`llm_guard.py` or similar)

---

## ✅ Next Steps

1. **Log and compare** the test vs real behavior:
   - Retrieved docs
   - Final messages
   - Token count
   - Model response

2. **Use the same logic** for hallucination filtering across both paths.

3. **Create a fallback system**: If no context retrieved, return `"I don't know."`

---

## 🧠 Suggested Utilities

- `logger.debug_retrieval(query, docs)`
- `logger.debug_tokens(messages)`
- `safe_messages_builder(messages, context_chunks)`
- `reject_response_if_no_overlap(response, context)`

---

## 📁 File Location Ideas

- `llm_guard.py` – context enforcement, prompt templates
- `logger_utils.py` – token logger, doc tracker
- `debug_tests.py` – test vs real comparison runner

---
