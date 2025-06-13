## ✅ Full Tech Stack Breakdown

This project uses the following technologies:

### 🌎 Environment
- **Library:** `dotenv` (`python-dotenv`)
- **Purpose:** Loads API keys and environment variables from a `.env` file securely.

### 🧠 Large Language Models (LLMs)
- **OpenAI GPT (`gpt-3.5-turbo`)**  
  → Generates high-quality textual answers via the **paid OpenAI API**.
  
- **Hugging Face Transformers (`microsoft/phi-2`)**  
  → Local/offline or Hugging Face-hosted model for **free** text generation (lighter, open-source).

### 📚 Embeddings
- **Library:** `sentence-transformers` (`all-MiniLM-L6-v2`)  
- **Purpose:** Converts text into numerical embeddings for **semantic similarity search**.

### 🗄️ Vector Database
- **Library:** `chromadb`  
- **Purpose:** Stores document embeddings and provides **semantic search** capability.

### 🔗 Document Store
- **Format:** `.txt` files located in `./data/example_business_docs`  
- **Purpose:** Acts as the **knowledge base** used to answer user questions.

### 🎒 Hugging Face Hub
- **Library:** `huggingface_hub`  
- **Purpose:** Authenticates with Hugging Face to download and manage transformer models like `phi-2`.

---

💡 **Next Steps:**  
You can fine-tune models, improve chunking strategies for large documents, or deploy this as a web service using **FastAPI** or **Streamlit** for interactive use.
