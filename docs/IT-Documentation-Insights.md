# YAP for Internal IT Documentation — Concept Review & Data-Ingestion Options

> Advisory note for Burak. **No code was changed** to produce this — it's a read-through of the
> repo as it stands plus practical options for your work use case (IT documentation at a Hyatt
> property, where OneNote's API is locked down by corporate).
> Date: 2026-06-01.

---

## 1. What YAP actually is (the concept)

YAP ("Your AI Partner") is a **Retrieval-Augmented Generation (RAG)** assistant. The idea is:

- You **don't train a model**. You take an off-the-shelf LLM and *ground* its answers in your own
  documents.
- Documents are **chunked → embedded → stored in a vector DB (ChromaDB)**.
- At question time, YAP **embeds the question, finds the most similar chunks, and stuffs them into
  the prompt** so the LLM answers from *your* content instead of from its memory (which reduces
  hallucination).
- The original target was **small/medium businesses** (FAQs, menus, policies). Your new target —
  **internal IT documentation** — is actually a *better* fit for RAG, because IT docs are factual,
  reference-heavy, and change often.

So the core value for your work is: **"ask a question in plain English, get an answer pulled
straight from our IT runbooks/procedures, with the source."**

---

## 2. The real state of the repo vs. the README (read this first)

There is a meaningful gap between what the **README describes** and what is **actually committed**.
This matters before you build on it.

| Area | README / docs claim (latest by date, 2025-08-16) | What's actually in the repo |
|------|--------------------------------------------------|------------------------------|
| LLM | Qwen 2.5 14B via vLLM (Phase 3, "current") | `app.py` has a phi-2 branch + a leftover OpenAI branch (see note below); real inference is the cloud vLLM endpoint, not committed |
| Retrieval | HyDE + Reciprocal Rank Fusion + adaptive thresholding | Plain top-3 cosine similarity |
| API | FastAPI `/ask` + `/ask/stream` streaming | None in repo (CLI `input()` loop only) |
| Auth | JWT login/registration | None in repo |
| Storage | SQLite users + chat history | ChromaDB only |
| Ingestion | OCR/PDF pipeline, chunking with metadata | `load_documents()` reads `.txt` only, **no chunking** |
| Modules | `ingest.py`, `embed.py`, `retriever.py`, `llm_interface.py` | **All four files are empty** |
| `requirements.txt` | implied full stack | **Empty file** |

**Interpretation of "the latest repo is not the main":** the lineage is
`LLM_Assistance` → renamed to → **`YAP-Your-AI-Partner`** (confirmed via the 2025-06-12 merge
commit). This repo *is* the latest. But the **most current statement of the concept is the README**
(the Qwen/vLLM phase), while the **most current working code that's committed** is still the
Phase-1 prototype. The advanced phases live in your **Colab + vLLM notebooks**, which were never
committed here. That's why "vLLM via cloud GPU is not running" doesn't block reading the code —
none of the vLLM code is in the repo to begin with.

**Action item before anything else:** `src/.env` is committed and contains
`OPENAI_API_KEY` and `HF_API_TOKEN` in a **public** repository.
👉 **Rotate both keys now**, add `.env` to `.gitignore`, and remove it from history. For a
Hyatt-data project this is non-negotiable.

---

## 3. Repurposing YAP for IT documentation

The good news: the architecture barely needs to change. A "business FAQ assistant" and an
"IT-docs assistant" are the same RAG shape. What changes is **the data sources** and **the
non-negotiable rule that data must never leave Hyatt's environment**.

What I'd reframe for the IT use case:
- **Ground every answer + always cite the source doc/page.** IT staff need to trust and verify.
  Your README already mentions "strict document-grounding" — keep that strict.
- **Keep a "last updated" date per chunk.** IT procedures go stale; surface the date so people
  know if an answer is current.
- **Self-hosted LLM only (the vLLM path), never the OpenAI path** for real Hyatt content — see §6.

---

## 4. The OneNote problem, stated plainly

OneNote's content is reachable programmatically only through the **Microsoft Graph API**, and Graph
requires either (a) an **app registration** in the tenant (Azure AD / Entra ID) or (b) **delegated
permission** for a signed-in user. At a Hyatt-managed tenant, corporate IT almost always:

- blocks self-service **app registration**, and
- restricts **admin consent** for Graph scopes like `Notes.Read`.

So "just call the OneNote API" is off the table unless corporate grants it. That's expected — and
there are several ways around it, ranging from "needs zero permission" to "ask IT nicely."

---

## 5. Data-ingestion options (ranked by how realistic they are inside a corporate tenant)

### Tier A — No special permission needed (start here)

1. **OneDrive / SharePoint local sync, then ingest the folder.**
   If your IT docs also live in SharePoint/Teams (most do), use the **OneDrive sync client** to sync
   those libraries to a local folder. YAP then ingests ordinary files on disk — **no API at all**.
   This is the single most reliable path and the one I'd build first.

2. **Manual OneNote export → files.**
   In the **OneNote desktop app**: `File → Export` a page / section / whole notebook to **PDF or
   DOCX** (or print-to-PDF). Drop those into YAP's ingest folder. Tedious, but needs zero IT
   approval and is great for a first proof-of-concept. Re-export when docs change.

3. **Manual upload UI.**
   Add a simple "drag-and-drop a PDF/DOCX/TXT" uploader (the README's Streamlit UI). Lets any IT
   teammate contribute docs without touching the filesystem.

### Tier B — Available in many tenants even when app registration is blocked

4. **Power Automate flow.**
   Power Automate is frequently enabled for end users even when Graph app registration isn't. A
   scheduled flow can read OneNote pages and **write them to a SharePoint library / OneDrive folder
   as files** — which YAP then ingests (see option 1). This gives you *near-automated* OneNote
   extraction without writing any Graph code yourself.

5. **ServiceNow Knowledge Base API.**
   Your README already lists ServiceNow as an integration target. If your IT KB/runbooks live in
   ServiceNow, its **Knowledge / Table API** is usually accessible with a service account and is a
   far cleaner source than OneNote. Strongly worth checking.

6. **Confluence / SharePoint pages / internal wiki.**
   If any docs are in Confluence or SharePoint pages, both have read APIs / export options that are
   typically less locked-down than OneNote.

### Tier C — Requires an explicit ask to corporate IT

7. **Sanctioned read-only Graph app.**
   Ask IT to register **one app** with **`Notes.Read` (read-only)** scope, scoped to your
   notebooks. Frame it as "read-only, data stays on a Hyatt-internal server, no content leaves the
   network." A narrow read-only ask is much easier to approve than broad access.

### Tier D — Last resort

8. **OCR / screen capture.**
   For content you can only *view* (locked PDFs, embedded images, screenshots), open the page and
   run **OCR** (the README mentions an OCR pipeline). Lossy and manual, but unblocks "trapped"
   content.

### Recommended sequence

> **Start: Tier A (local sync + manual export) for a working demo → then Tier B (Power Automate /
> ServiceNow) to automate refresh → only escalate to Tier C if you need live OneNote sync.**

---

## 6. The compliance point you can't skip

This is the most important paragraph in the document.

**Correction (per Burak):** the **OpenAI key/branch in `app.py` is leftover and not actually
used** — real inference goes through your **cloud vLLM (Qwen) endpoint running on RunPod**. So
OpenAI isn't the exposure. The real question becomes: **is RunPod an acceptable place to send
Hyatt internal IT-doc content?** RunPod is a **third-party GPU cloud outside Hyatt's network**, so
sending it the question + retrieved internal-doc context is the same policy problem as OpenAI was —
just relocated to your own pod.

For your work build:
- **Clean up the dead OpenAI branch** so no one can accidentally route Hyatt data to it, and remove
  the unused `OPENAI_API_KEY`.
- **RunPod is great for a demo/POC — and probably fine for *sanitized* example data.** It is **not**
  automatically OK for real Hyatt IT docs without security sign-off, because the data leaves
  Hyatt's network to a vendor. Treat that as an approval question, not a technical one.
- **If you do run real data on RunPod, harden it:**
  - Use **Secure Cloud** (SOC2 / T3-T4 data centers), **not Community Cloud** (which is peer-hosted
    on strangers' machines — never put corporate docs there).
  - Use a **dedicated pod**, keep it **ephemeral**, and **don't persist docs/embeddings/chat logs on
    the pod** — pull them from, and write them back to, somewhere you control.
  - Lock the endpoint down: **auth on the vLLM API, TLS, IP allow-listing**, no public exposure.
  - Remember RunPod is **compute, not a data processor agreement** — there's typically no BAA/DPA
    covering your content, which is exactly what corporate security will ask about.
- **The fully-compliant target** is the model running on **infrastructure Hyatt controls** — a
  Hyatt-approved cloud tenant/VPC or on-prem GPU (your `scalibility.md` Level 2/3). RunPod sits at
  **Level 1.5**: real GPUs you rent, but still a third party.
- The **embedding model (`all-MiniLM-L6-v2`) already runs locally** — good, keep it that way.
  Embeddings of sensitive text should never go to a hosted embedding API either.
- Keep chat history + logs (the SQLite/CSV layer) **on the internal server**, and treat them as
  sensitive — they'll contain snippets of internal docs.

---

## 7. Concrete gaps to close to make it real (no action taken — just the list)

These are the things that are *described* but not yet *built*, in rough priority order:

1. **Real ingestion** — multi-format (PDF/DOCX/MD/HTML) + **chunking with metadata**
   (source filename, page/heading, last-updated date). Today it's whole-`.txt`-as-one-blob.
2. **Fill the empty modules** — `ingest.py`, `embed.py`, `retriever.py`, `llm_interface.py` are
   stubs; the logic is all crammed in `app.py`.
3. **Populate `requirements.txt`** so the project is reproducible/installable.
4. **Source citations in answers** — return which doc/chunk each answer came from.
5. **Folder-watch / scheduled re-ingest** so synced docs stay fresh.
6. **The vLLM client** that the README describes (streaming, context enforcement) — commit it from
   your Colab work so it's not lost.
7. **Secrets hygiene** — `.env` out of git, keys rotated.

---

## 8. Suggested next step

The cleanest path to a useful internal tool, given the OneNote constraint:

1. Sync (or export) a small set of real IT runbooks into a local folder.
2. Build proper **chunking + multi-format ingestion**.
3. Point YAP at your **private vLLM/Qwen endpoint only**.
4. Add **citations** + a **manual upload box**.
5. Demo it to your team; *then* ask IT about Power Automate or a read-only Graph app to automate
   the OneNote pull.

That gets you a working, **policy-safe** IT-docs assistant without ever depending on the blocked
OneNote API.
