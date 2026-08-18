# YAP — Local, Private IT Knowledge Base

A completely **local** AI assistant for IT work. Load your own IT documentation
(SOPs, network docs, configs, PDFs, Word, Excel, notes…) and ask questions about
it. Answers are grounded in **your** documents via RAG and always show their
**sources** — and the assistant refuses to invent things it can't find.

- 🔒 **Local-first / private** — documents, embeddings, vector DB and the LLM all
  run on your machine. No external AI API. No internet needed to answer questions.
  No telemetry, no document upload to third parties.
- 🧠 **Qwen 2.5 3B** (chat) + **nomic-embed-text** (embeddings) via **Ollama**.
- 📚 **RAG** with metadata filtering, similarity threshold, and source citations.
- 🗂 **Document management** — upload / re-index / delete, with metadata (site,
  version, date, author, …).
- 🚫 **Hallucination control** — if it isn't in your documents, it says so.

> Swapping the model later is one line in `.env` — the architecture doesn't depend
> on the 3B model.

---

## Architecture

```
Frontend (SPA)  ──►  FastAPI backend  ──►  ┌ Document Service (parse + chunk)
   Chat / Docs                             ├ RAG Service (embed + search + rank)
   Search / Dashboard                      └ Chat Service (Qwen 2.5 3B)
                                                    │
                        ChromaDB (vectors, local) ──┘   SQLite (doc registry)
                        Ollama (Qwen + embeddings, local)
```

Everything runs on one computer. See `docs/` for the deeper design rationale.

---

## Prerequisites

1. **Python 3.10+**
2. **[Ollama](https://ollama.com)** installed and running, with the models pulled:
   ```bash
   ollama pull qwen2.5:3b
   ollama pull nomic-embed-text
   ```

## Run

```bash
./run.sh
```
That creates a virtualenv, installs dependencies, copies `.env.example` → `.env`
(first run), and starts the app at **http://127.0.0.1:8000**.

### Install as an always-on service (recommended)

```bash
./install.sh
```
Sets YAP up as a **systemd service** so it starts on boot and auto-restarts — no need to keep a
terminal open. If **Tailscale** is installed, it also publishes YAP over **HTTPS** (valid cert, no
"not secure" warning) so phones can install it as a proper app.

- Manage: `sudo systemctl {status|restart|stop} yap`
- Logs: `journalctl -u yap -f`
- Update: `git pull && sudo systemctl restart yap`
- Reach from other devices on your LAN: set `HOST=0.0.0.0` in `.env`, then restart.

<details><summary>Manual start (instead of run.sh)</summary>

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
</details>

## First use

1. Open **http://127.0.0.1:8000**. On first run you create the **super-admin** account (using the
   setup key printed in the server terminal). Accounts are **invite-only** — the super-admin/admins
   create users from the **Users** page. Toggle **light/dark** from the top bar.
2. **Properties (multi-tenant):** each property/site is an **isolated knowledge base** (its own
   vector collection). Users are scoped to one property; the **super-admin** manages properties and
   can switch between any of them with the property picker in the top bar.
2. **Documents** → upload a PDF/DOCX/XLSX/TXT/MD/CSV (optionally set Site, Version, Date…), or drop
   many exported files into `data/import/` and click **Import from folder**.
3. Go to **Chat** and ask a question. The answer cites the documents it used.
4. **Search** inspects the index directly (no AI); **Integrations & Security** shows connector/M365
   authorization status; **Dashboard** / **Settings** show stats and system/model status.

## Configuration (`.env`)

| Key | Default | Meaning |
|-----|---------|---------|
| `CHAT_MODEL` | `qwen2.5:3b` | Ollama chat model |
| `EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `250` / `50` | chunking (words) |
| `TOP_K` | `5` | chunks retrieved per question |
| `SIMILARITY_THRESHOLD` | `0.2` | drop weak matches (0–1) |
| `MAX_CONTEXT_CHARS` | `6000` | context size sent to the model |
| `MAX_UPLOAD_MB` | `25` | upload size limit |

## Security

- **Authentication:** all data endpoints require a signed session token. First run creates an admin
  account; passwords are scrypt-hashed, tokens are HMAC-signed and expiring, login is rate-limited.
  The signing key auto-generates in `data/secret.key` (gitignored).
- **HTTP hardening:** security headers (CSP, `X-Frame-Options: DENY`, `nosniff`, no-referrer) on
  every response; unhandled errors return a generic message (no internals leaked).
- `.env` and `data/` are gitignored; **never commit secrets**.
- Uploads are extension-checked, size-limited, filename-sanitised, and stored under generated names
  (no path traversal). The LLM cannot execute shell commands; documents cannot execute code.
- Retrieved document text is treated as **untrusted data** — the model is
  instructed never to follow instructions embedded in it (prompt-injection defence).
- Binds to `127.0.0.1` by default. For remote access use a private VPN (e.g. Tailscale), **not** a
  public port-forward.

## Project layout

```
backend/
  config.py            settings (.env)
  main.py              FastAPI app
  models.py            request/response schemas
  routers/             chat, documents, search, system
  services/            documents, embeddings, vectorstore, rag, chat, ingestion, registry
  utils/security.py    upload validation
frontend/              index.html, styles.css, app.js  (served by FastAPI)
tests/                 parsing/chunking tests
docs/                  architecture & design docs
```

## Tests

```bash
pip install pytest
pytest -q
```

## Roadmap

Phase 2 email/document intelligence (OCR, thread reconstruction) · Phase 3 network
config parsing (ciscoconfparse2 / Batfish) · Phase 4 Teams/tickets · Phase 5
multi-user + RBAC. See `docs/IT-Copilot-Build-Plan.md`.
