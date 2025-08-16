YAP – Your AI Partner

Business LLM Assistant (Prototype)

🎯 Objective

YAP is a prototype for building lightweight, domain-specific AI assistants tailored for small and medium businesses (SMBs).

Instead of training giant LLMs, YAP enhances retrieval-augmented generation (RAG) with business-specific data (FAQs, menus, policies, booking APIs). It runs locally on CPU or can scale to GPU inference servers for more advanced performance.

✨ Key Features

✅ RAG-powered answers grounded in real business data

✅ Smart Retrieval → HyDE + Reciprocal Rank Fusion (RRF)

✅ Flexible deployment → local CPU mode or GPU-accelerated inference

✅ Persistent storage → ChromaDB for documents, SQLite for user data + chat history

✅ Authentication → JWT-based login/registration

✅ Extensible APIs → Stripe (payments), OpenTable (bookings), ServiceNow (IT tickets)

✅ Modern UI → Streamlit frontend with Apple-like theme, chat history, and streaming answers

⚙️ How It Works

Ingest & Chunk

Ingest FAQs, menus, PDFs, policies, and structured text

Split into metadata-rich chunks (filename, heading, position)

Embedding & Storage

Embeddings: all-MiniLM-L6-v2 (sentence-transformers)

Stored in ChromaDB for retrieval

Smart Retrieval

HyDE (Hypothetical Document Embeddings)

RRF (Reciprocal Rank Fusion)

Adaptive thresholding to filter irrelevant chunks

LLM Inference

Phase 1 – Flan-T5 (CPU) → fast, lightweight baseline

Phase 2 – Mistral-7B (GPU, Colab vLLM) → improved accuracy, longer context

Phase 3 – Qwen 2.5 (14B, GPU, Colab vLLM) → extended 32k context, fewer hallucinations, better grounding

Answer Generation

Strict document-grounding with hallucination rejection

Streaming responses for smoother UX

🚀 Evolution & Upgrades
🔹 Phase 1 – Early CPU Prototype

Model: Flan-T5-Small

Inference: Hugging Face pipeline (text2text-generation)

Strength: lightweight, no GPU needed

Limitation: short context, weak performance on complex queries

🔹 Phase 2 – Mistral Upgrade

Model: Mistral-7B-Instruct via vLLM

Hosted on Google Colab GPU

Gained: better reasoning, longer context (4k tokens), streaming APIs

Added: hallucination filtering + context enforcement

🔹 Phase 3 – Qwen Migration (Current)

Model: Qwen 2.5 (14B) via vLLM

Hosted on Colab GPU, 32k token context

Strong multilingual + reasoning abilities

Current production setup for GPU mode

🔧 Recent Additions (2025)

🧩 Smart RAG → HyDE + RRF scoring for robust retrieval

🔒 JWT Authentication → per-user sessions + secure API calls

🗄 Persistence Layer → SQLite (users, chat history) + ChromaDB (docs)

💾 OCR Pipeline → PDF ingestion + structured chunking

🖥 Frontend UI → dark theme, login, chat history, 3D animated background

🌐 API Endpoints → /ask & /ask/stream with FastAPI integration

📊 Logging → CSV exports + debug-friendly logs

🧠 Technical Notes

Embeddings: MiniLM (all-MiniLM-L6-v2)

Vector DB: ChromaDB (persistent collections)

Inference Modes:

Local/CPU → Flan-T5-Small (fast prototyping)

GPU/Colab → Mistral-7B, now Qwen 2.5 14B (production-ready)

Security: JWT + HTTPS-ready, hallucination rejection filters

Token Handling: Dynamic allocation, truncation for overflow

💡 Next Steps

🚀 Deploy GPU inference on AWS/GCP for reliability beyond Colab

📱 Add multi-channel access (SMS, WhatsApp, Teams, SIP phone)

📑 Build onboarding templates for SMBs (menus, refund policies, bookings)

📊 Admin dashboard → retrieval accuracy monitoring + user analytics

⚡ YAP has evolved from a local Flan-T5 CPU demo → to Mistral-7B GPU inference → to Qwen 2.5 (14B) with 32k context.
It is now a hybrid assistant platform, lightweight for SMBs yet scalable with cloud GPU when needed.
