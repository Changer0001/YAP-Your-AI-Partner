import os
import logging
import chromadb
from myapp.embed import embedding_model, chunk_text

# ✅ Set up persistent ChromaDB client
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="example_business_docs")

def load_documents(folder_path):
    docs = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.endswith(".txt") and os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        docs.append((filename, content))
            except Exception as e:
                logging.warning(f"Failed to read {filename}: {e}")
    return docs

def ingest_and_store(docs):
    idx = 0
    for filename, doc in docs:
        chunks = chunk_text(doc)
        for chunk in chunks:
            try:
                embedding = embedding_model.encode(chunk).tolist()
                chunk_id = f"{filename}_{idx}"
                collection.add(documents=[chunk], embeddings=[embedding], ids=[chunk_id])
                idx += 1
            except Exception as e:
                logging.warning(f"Failed to ingest chunk from {filename}: {e}")
    logging.info(f"Ingested {idx} chunks into ChromaDB.")
