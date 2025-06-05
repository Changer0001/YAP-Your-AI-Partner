# 🧑‍💻 Usage Guide

Once you've installed the project and completed the setup, follow this guide to use your LLM Business Assistant.

---

## 1️⃣ Add Your Business Documents

Place your internal documents into the `data/` folder. Supported formats:

- `.txt`
- `.md`
- `.pdf`

Example:

data/
├── faq.txt
├── return_policy.pdf
└── employee_handbook.md


---

## 2️⃣ Ingest and Index the Documents

Run the ingestion script to parse and chunk the documents, generate embeddings, and store them in the vector database:

```bash
python scripts/ingest_documents.py
```
You should see output like:

Loaded 3 documents
Split into 75 chunks
Stored 75 embeddings in Chroma

# 3️⃣ Ask Questions (CLI)

Start the assistant:
python main.py

Then type your questions:
❓ What is our return policy for holiday purchases?
🤖 "Customers have 30 days to return items purchased during the holiday season..."
