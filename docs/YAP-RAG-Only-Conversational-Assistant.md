# YAP — RAG-Only Conversational Assistant

> Version: 1.0 • Date: 2025-08-12  
> Owner: _Your Team_  
> Scope: Backend policy + UI/UX updates to enforce **RAG-only** answers while keeping friendly small-talk.

---

## Overview

This release makes YAP conversational for greetings/thanks while enforcing **closed-book** behavior for all substantive queries: answers are generated **only** when the retrieval layer (RAG) supplies relevant evidence (uploaded docs, approved web snapshots, or vetted chat snippets). Otherwise YAP responds with **“I don’t know.”**

The Streamlit UI has also been modernized with a glassy blue theme and improved ergonomics.

---

## Goals

- ✅ Friendly small-talk (“hello”, “how are you?”, “thanks”, “bye”).  
- ✅ **RAG-only** answers for business/policy/technical questions.  
- ✅ Streaming SSE contract (`event: sources` → token `data` → `event: done`).  
- ✅ Modern, consistent chat UI.

---

## High-Level Changes

### Backend (Policy & Safety)

- **Strict RAG gate** for non-small-talk queries in `/ask` and `/ask/stream`:
  - If retrieval returns no rows, empty context, or lexical relevance `< 0.15` → respond **“I don’t know.”**
- **Small-talk pass-through**:
  - Regex detectors for greeting/thanks/goodbyes/“how are you”.
  - `_smalltalk_reply(...)` produces short, friendly responses (optional name capture stored in memory).
- **Hallucination guard** in `app/llm/llm_interface.py`:
  - Stopword-aware Jaccard overlap between generated answer and supplied context; if `< 0.08` ⇒ reject with **“I don’t know.”**
- **Context-only prompting**:
  - System instruction mandates: *use only provided context; otherwise say “I don’t know.”*

### Frontend (UX)

- Enter-to-send via `st.chat_input`.
- Glassy right panel wrapping chat to match YAP bubble.
- Sidebar with gear dropdown (Clear chat / Log out; optional Offline toggle).
- Brand header with “YAP” in gradient Orbitron.

---

## Files Touched

- `app/api/api_routes.py`
- `app/llm/llm_interface.py`
- Streamlit app (styles + layout; no behavior change required for RAG policy)

---

## Backend Details

### Small-Talk Detection (server-side)

- Regexes detect:
  - Greeting: `hi|hey|hello|good morning/afternoon/evening`
  - Thanks: `thanks|thank you|appreciate`
  - Goodbye: `bye|good night|see you|take care`
  - How-are-you: `how are you|how’s it going|how are things`

- `_smalltalk_reply(question, name)` returns one of:
  - “Hey, _{name}_! How can I help today?”
  - “I’m doing well—thanks for asking, _{name}_! How can I help?”
  - “You’re welcome! Anything else I can do?”
  - “Take care! Ping me anytime.”

### RAG Gate (server-side)

- Quick lexical relevance `_ctx_relevance(question, rows)` compares question tokens to the top retrieved text:
  - If `(not rows) or (not ctx) or (relevance < 0.15)` and **not small-talk** ⇒ **“I don’t know.”**
- Threshold `0.15` is tunable (see _Configuration_).

### Hallucination Guard (LLM layer)

- Stopword-aware Jaccard overlap between **answer** and **doc context**; if `< 0.08` and not small-talk ⇒ **“I don’t know.”**

---

## API Contract

### `POST /ask`

- **Input**: 
  ```json
  {
    "question": "...",
    "collection": "example_business_docs",
    "use_hyde": true,
    "k_final": 6,
    "history": []
  }
  ```
- **Behavior**:
  1. Normalize history; retrieve via RRF + HYDE.
  2. If **small-talk** → respond conversationally (no RAG required).
  3. Else apply **RAG gate**. On fail → `{'answer': 'I don’t know.', 'sources': []}`
  4. On pass → call LLM with fused context; save history.
- **Output**: 
  ```json
  {
    "question": "...",
    "answer": "...",
    "sources": [ { "id": "...","title": "...","url": "...","page": 1 } ]
  }
  ```

### `POST /ask/stream` (SSE)

- **Order**:
  1. `retry: 2000`
  2. `event: sources` + JSON array (may be `[]`)
  3. Stream deltas: `data: {"choices":[{"delta":{"content":"..."}}]}`
  4. `event: done`
- **Out-of-scope path**:
  - Sends empty `sources`, then a single **“I don’t know.”** delta, then `done`.

---

## Key Snippets

### RAG Gate (API)

```python
relevance = _ctx_relevance(req.question, rows)
if not _is_smalltalk_text(req.question) and ((not rows) or (not ctx.strip()) or (relevance < 0.15)):
    answer = "I don’t know."
    save_chat_history(user_id, req.question, answer)
    return { "question": req.question, "answer": answer, "sources": [] }
```

### Small-Talk Reply (LLM Interface)

```python
if _is_smalltalk_text(question) and not (doc_context and doc_context.strip()):
    name = _extract_name(question) or _extract_name(history_blocks if isinstance(history_blocks, str) else "")
    if user_id and name: _save_memory(user_id, "user_name", f"User introduced as {name}")
    return _smalltalk_reply(question, name)   # (yield in streaming version)
```

### Hallucination Guard (LLM Interface)

```python
if should_reject_answer(answer, doc_context, intent):
    return "I don't know."
```

---

## Configuration & Tunables

| Setting | Location | Default | Notes |
| --- | --- | --- | --- |
| Relevance threshold | `api_routes._ctx_relevance` | `0.15` | Increase to be stricter (`0.18–0.20`); decrease to reduce false negatives (`0.12–0.14`). |
| Answer-context Jaccard | `llm_interface.should_reject_answer` | `0.08` | Raise to be stricter on hallucinations. |
| Max context tokens | env `MAX_TOKENS` | `32768` | Overall token budget; enforced in `llm_core`. |
| Reserved completion | env `RESERVED_COMPLETION` | `1536` | Guarantee space for generation. |

---

## Test Plan (Smoke)

1. **Small-talk**  
   Request: `hello` → Friendly greeting (no RAG needed).

2. **Out-of-scope**  
   Request: `what is baklava?` → `"I don’t know."` and `sources: []`.

3. **In-scope**  
   Request: `What is our refund policy?` → Grounded answer with non-empty `sources`.

4. **Streaming SSE**  
   Use `/ask/stream` → Verify `event: sources` → token `data` → `event: done`.

---

## Known Limitations

- Relevance gate is heuristic; for higher precision, use retriever **similarity scores** (e.g., cosine ≥ `0.45–0.55`) or re-rankers.
- If enabling web RAG, use **domain allowlists** and **snapshot caching**.
- Inline citations (`[S1]`) are not enforced yet; can be added and validated post-generation.

---

## Changelog (Summary)

- Added small-talk detection and friendly replies; name capture to memory.
- Enforced **RAG-only** answers via lexical relevance gate in `/ask` & `/ask/stream`.
- Hallucination guard using stopword-aware Jaccard overlap.
- Streamlined SSE sequence; always emit `sources` first.
- Modernized Streamlit UI (glassy theme, cleaner bubbles, sidebar actions).
- Fixed CSS rendering as text by moving to top-level, unindented style injection.

---

## Deployment

1. Ensure `VLLM_API_URL` and model env vars are set.  
2. Run API: `uvicorn app.main:app --reload`  
3. Start Streamlit app; log in and run smoke tests above.

---

## Appendix: Function Signatures

- `build_context_from_collection(query, collection, use_real_hyde=True, k_final=6) -> (ctx: str, rows: List[Tuple[id, text, meta]])`
- `ask_llm_hf(question, history_blocks, doc_context, user_id) -> str`
- `ask_llm_hf_stream(question, history_blocks, doc_context, user_id) -> Generator[str]`

---

**Outcome:**  
YAP now **chats politely** yet answers **only** when retrieval supplies **relevant evidence**. The UI is clean, glassy, and aligned with the brand’s blue theme.
