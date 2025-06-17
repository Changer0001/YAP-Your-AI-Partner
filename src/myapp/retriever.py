import os
import logging
import chromadb
from myapp.embed import embedding_model

# ✅ Setup Chroma client
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="example_business_docs")

def retrieve(query):
    try:
        query_embedding = embedding_model.encode(query).tolist()
        results = collection.query(query_embeddings=[query_embedding], n_results=3)

        if not results.get("documents") or not results["documents"][0]:
            logging.warning("No documents retrieved from ChromaDB.")
            return ""

        docs = results["documents"][0]
        logging.debug(f"Retrieved {len(docs)} documents: {docs}")

        combined = "\n---\n".join(docs)
        if len(combined) > 1000:
            combined = combined[:1000] + "..."

        return combined

    except Exception as e:
        logging.error(f"Retrieval failed: {e}")
        return ""
