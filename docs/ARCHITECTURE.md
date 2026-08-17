# Architecture

Local, private IT Copilot. Everything runs on one machine; Microsoft 365 is an **optional**
read-only source, never a dependency.

```
                         IT COPILOT (all local)
                                │
         ┌──────────────────────┴───────────────────────┐
   Local Knowledge (always on)                 Microsoft 365 (optional)
   uploads · import folder                     export files (default) /
   local documents                             delegated Graph read (if approved)
         └──────────────────────┬───────────────────────┘
                                ▼
                 Ingestion: parse → chunk → metadata/provenance → embed
                                ▼
        ┌───────────────┬───────────────┬──────────────────┐
     Intent router   RAG (hybrid-ready) Registry (SQLite)  Vector store (Chroma)
        │               │                                     │
        └───────────────┴──────────────── context + citations ┘
                                ▼
                       Qwen 2.5 3B (Ollama, local)
                                ▼
                     Frontend SPA (served by FastAPI)
```

## Components
- **Frontend** (`frontend/`) — SPA: Dashboard, Chat, Documents, Search, Integrations & Security,
  Settings. Served by FastAPI; no build step.
- **Backend** (`backend/`) — FastAPI. `routers/` (chat, documents, search, system, integrations),
  `services/` (intent, rag, chat, embeddings, vectorstore, documents, ingestion, registry).
- **Connectors** (`connectors/`) — `local/` (available) and `microsoft/` (metadata + status only;
  no real access until approved). Authorization is separate from ingestion.
- **Storage** — ChromaDB (vectors) + SQLite (registry). See `DATA_SECURITY.md`.
- **AI** — Qwen 2.5 3B (chat) + nomic-embed-text (embeddings), both local via Ollama.

## Principles
Local AI · company-controlled data · least privilege · no authorization bypass · traceable
provenance · RAG quality over model size · M365 optional.

## Request flow
`question → intent router →` (conversational → deterministic reply) `| (knowledge → RAG: embed →
metadata filter → search → threshold → rank → context) → Qwen → answer + citations`.

See `RAG.md`, `CONNECTORS.md`, `MICROSOFT_365_AUTHORIZATION.md`, `DATA_SECURITY.md`, `EXPORT_GUIDE.md`.
