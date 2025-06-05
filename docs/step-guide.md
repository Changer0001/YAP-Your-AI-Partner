# ⚙️ Setup Guide

This guide will walk you through setting up the LLM Business Assistant locally.

---

## 📦 Prerequisites

Before you begin, make sure you have the following installed:

- **Python 3.10+**
- **pip** (Python package manager)
- Optional (for UI): **Node.js + npm** (for React frontend)

---

## 🔧 Installation Steps

1. **Clone the repository**

```bash
git clone https://github.com/your-username/llm-business-assistant.git
cd llm-business-assistant
```
# Installing Dependencies

pip install -r requirements.txt

# Set up Environment Variables

Create a .env file in the root directory:
OPENAI_API_KEY=your-openai-api-key
🔐 If you're using a local LLM like phi-2, the API key isn't needed.

# 📁 Folder Structure (Simplified)

llm-business-assistant/
├── data/                 # Raw business documents (.pdf, .txt, .md)
├── embeddings/           # Stored vector files (Chroma/FAISS)
├── scripts/              # Preprocessing & ingestion scripts
├── llm/                  # LLM interface
├── api/                  # (Optional) FastAPI backend
├── ui/                   # (Optional) Frontend interface
└── main.py               # Entry point for the assistant

# ▶️ Run the App (Basic CLI)
1 - Ingest your documents:
python scripts/ingest_documents.py
2 - Start the assistant:
python main.py
3 - Ask your questions (via CLI or integrated UI)
Example:
"What is our refund policy on gift items?"

# 🌐 Run the API (Optional)
uvicorn api.app:app --reload


