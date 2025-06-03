# 🧠 LLM Business Assistant – Architecture & Documentation

## 📌 Project Goal

Build a lightweight, independent LLM assistant for small businesses that can:
- Answer business-specific questions
- Use internal data (FAQs, policies, documents)
- Run without training large models
- Work locally without GPUs

This project uses **RAG (Retrieval-Augmented Generation)** to inject private/business-specific knowledge into a lightweight language model’s responses

## ⚙️ How It Works (System Architecture)

### Step-by-Step Flow:

1. **Document Ingestion**
   - Load business files (`.txt`, `.md`, `.pdf`)
   - Chunk text into small pieces for retrieval
  
2. **Embedding Generation**
   - Convert each text chunk into a vector using a sentence transformer

3. **Vector Store**
   - Store embeddings in a vector database (e.g., Chroma, FAISS)

4. **Question Answering**
   - User asks a question
   - Search the vector DB for relevant chunks
   - Inject retrieved text into prompt
   - Use small LLM (like `phi-2` or OpenAI GPT) to generate an answer

## 🧱 Tech Stack

| Component         | Tool / Library                           |
|------------------|------------------------------------------|
| Language          | Python                                   |
| Document Parsing  | LangChain / PyPDF                        |
| Embeddings        | SentenceTransformers (MiniLM or similar) |
| Vector DB         | Chroma                                   |
| LLM               | `phi-2`, OpenAI API, or similar          |
| Backend (optional)| FastAPI                                  |
| Frontend (optional)| React or plain HTML/JS                  |


## 🔁 Workflow Diagram
