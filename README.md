# YAP – Your AI Partner  
**Business LLM Assistant (Prototype)**  

---

## 🎯 Objective  
YAP is a prototype for building **lightweight, domain-specific AI assistants** tailored for small and medium businesses (SMBs).  

Instead of training massive LLMs, YAP enhances **retrieval-augmented generation (RAG)** with business-specific data (FAQs, menus, policies, booking APIs).  
It runs **locally on CPU with quantized models** or scales to **GPU inference servers** (Mistral/Qwen) for advanced performance.  

---

## ✨ Key Features  
- ✅ **RAG-powered answers** grounded in real business data  
- ✅ **Smart Retrieval** → HyDE + Reciprocal Rank Fusion (RRF)  
- ✅ **Multiple inference modes** → quantized CPU or full-scale GPU  
- ✅ **Persistent storage** → ChromaDB for documents, SQLite for user data + chat history  
- ✅ **Authentication** → JWT-based login/registration  
- ✅ **Extensible APIs** → Stripe (payments), OpenTable (bookings), ServiceNow (IT tickets)  
- ✅ **Modern UI** → Streamlit frontend with Apple-like theme, chat history, and streaming answers  

---

## ⚙️ How It Works  
1. **Ingest & Chunk**  
   - Upload FAQs, menus, PDFs, policies, or scrape websites  
   - Split into metadata-rich chunks (filename, heading, position)  

2. **Embedding & Storage**  
   - Embeddings generated with `all-MiniLM-L6-v2`  
   - Stored in **ChromaDB** (persistent collections)  

3. **Smart Retrieval**  
   - HyDE (Hypothetical Document Embeddings)  
   - RRF (Reciprocal Rank Fusion)  
   - Adaptive thresholding to filter irrelevant chunks  

4. **LLM Inference**  
   - **Phase 1 – Flan-T5 (CPU, Quantized)**  
     - Hugging Face pipeline (`text2text-generation`)  
     - Used **quantization (8-bit)** for speed  
     - Pros: no GPU required, fast startup  
     - Cons: weaker accuracy, small context window  

   - **Phase 2 – Mistral-7B (GPU, Colab vLLM)**  
     - Hosted via **vLLM** server on Colab  
     - Added **streaming APIs**, better reasoning, ~4k token context  
     - Introduced **hallucination rejection + context enforcement**  

   - **Phase 3 – Qwen 2.5 (14B, GPU, Colab vLLM)** *(Current)*  
     - Migration to **Qwen 2.5 Instruct** with **32k token context**  
     - Runs on GPU (Colab vLLM)  
     - Better multilingual, reasoning, and factual grounding  

5. **Answer Generation**  
   - Strict **document-grounding** (rejects unsupported answers)  
   - **Streaming output** for smooth UI  

---

## 🚀 Evolution & Upgrades  

### 🔹 Phase 1 – Early CPU Prototype  
- Model: **Flan-T5-Small**  
- Setup: CPU-only, Hugging Face pipeline  
- Optimizations: **quantization** (8-bit) for faster inference  
- Strength: runs anywhere, no GPU  
- Limitation: small context, weaker performance  

### 🔹 Phase 2 – Mistral Upgrade  
- Model: **Mistral-7B-Instruct-v0.2**  
- Hosted on **Colab GPU via vLLM**  
- Features: streaming responses, hallucination rejection  
- Context window: **4k tokens**  

### 🔹 Phase 3 – Qwen Migration (Current)  
- Model: **Qwen 2.5 (14B Instruct)**  
- Hosted on **Colab GPU via vLLM**  
- Context window: **32k tokens**  
- Best accuracy, reasoning, and retrieval performance so far  

---

## 🔧 Recent Additions (2025)  
- 🧩 **Smart RAG** → HyDE + RRF scoring  
- 🔒 **JWT Authentication** → secure user sessions  
- 🗄 **Persistence Layer** → SQLite (users, chat history) + ChromaDB (docs)  
- 💾 **OCR Pipeline** → PDF ingestion support  
- 🖥 **Frontend UI** → Streamlit dark theme, Apple-like design, login & chat history  
- 🌐 **API Endpoints** → `/ask` & `/ask/stream` with FastAPI  
- 📊 **Logging** → CSV exports + monitoring  

---

## 🧠 Technical Notes  
- **Embeddings:** `all-MiniLM-L6-v2`  
- **Vector DB:** ChromaDB  
- **LLMs Used (Chronological):**  
  1. **Flan-T5-Small (quantized)** – CPU baseline  
  2. **Mistral-7B (vLLM, GPU)** – stronger reasoning  
  3. **Qwen 2.5 14B (vLLM, GPU)** – current production, 32k context  
- **Token Handling:** dynamic budget allocation, truncation for overflow  
- **Security:** JWT auth, HTTPS-ready, hallucination filtering  
