# Data Security — what is stored, where, and how to delete it

> The app is **local-first**. Company data stays on your machine. This documents exactly what is
> stored, what leaves the computer, and how to wipe it.

## What leaves the computer
- **Nothing about your content** goes to any external AI service. Qwen 2.5 3B and the embedding
  model run **locally via Ollama**; question + retrieved context are sent only to `127.0.0.1`.
- **One-time, content-free** outbound: downloading the model (`ollama pull`) and installing Python
  packages. No telemetry — ChromaDB telemetry is explicitly **disabled**.
- If (and only if) you later enable a Microsoft Graph connector, the app talks to Microsoft Graph to
  **read** approved data **into** local storage — it never sends your data outward to a third party.

## What is stored locally, and where
All under the app's data directory (default `./data/`, configurable via `DATA_DIR`):

| What | Location | Contents |
|------|----------|----------|
| Original files | `data/uploads/` | the documents you upload/import (stored under generated names) |
| Import drop folder | `data/import/` | files you place for bulk import |
| Vector index | `data/chroma/` | embeddings + chunk text + provenance metadata |
| Document registry | `data/registry.sqlite3` | filenames, metadata, status, chunk counts, content hashes |
| Config/secrets | `.env` (repo root) | settings and (future) connector IDs — **gitignored** |
| Conversation history | browser `localStorage` | your chat, on your machine only |

## Encryption
- **At rest:** the app relies on **full-disk encryption** (enable LUKS on Linux / BitLocker /
  FileVault). This is the recommended and simplest protection for a single-machine local app.
- **Secrets:** kept in `.env` (gitignored) — never committed. Future Microsoft tokens will be held
  in the OS secret store / an encrypted token cache, never in plaintext in the repo.
- **Not separately encrypted:** the Chroma index and SQLite registry are protected by filesystem
  permissions + full-disk encryption, not app-level field encryption (a possible future hardening
  step for a multi-user deployment).

## Secrets never become searchable
Before indexing, a redaction step (Phase-6 target; design in `docs/Enterprise-Knowledge-Architecture.md`)
detects passwords/keys/tokens and keeps them out of the vector index and out of model prompts.

## File-permission hygiene
- The server binds to **`127.0.0.1`** only (not exposed on the network).
- Uploads are extension-checked, size-limited, filename-sanitised, and stored under generated names
  (no path traversal). The LLM cannot run shell commands; documents cannot execute code.
- Recommended: `chmod 700 data/` so only your user can read the knowledge base.

## How to delete data
- **One document:** Documents tab → **Delete** (removes the file, its chunks, and its registry row).
- **Everything (knowledge base):** stop the app and delete `data/chroma/`, `data/registry.sqlite3`,
  `data/uploads/`, `data/import/`. Restart — you're back to empty.
- **Conversation history:** Chat tab → **Clear conversation** (clears browser `localStorage`).
- **Connector credentials (future):** an in-app "Disconnect / revoke" action deletes the local token
  cache; you also revoke consent in **My Account → App permissions**.

## Boundary the app enforces
```
Application config  ≠  Knowledge base  ≠  Conversation memory  ≠  M365 source data
```
The LLM only ever receives the **minimum retrieved context** for the current question, never the
whole store, and can't modify any of these.
