import os
import chromadb
import logging
from myapp.embed import embedding_model, chunk_text

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="example_business_docs")

def load_documents(folder_path):
    docs = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.endswith(".txt") and os.path.isfile(file_path):
            with open(file_path, 'r', encoding="utf-8") as f:
                docs.append(f.read())
    return docs

def ingest_and_store(docs):
    idx = 0
    for doc in docs:
        chunks = chunk_text(doc)
        for chunk in chunks:
            embedding = embedding_model.encode(chunk).tolist()
            collection.add(documents=[chunk], embeddings=[embedding], ids=[f"doc_{idx}"])
            idx += 1
    logging.info(f"Ingested {idx} chunks into ChromaDB.")
