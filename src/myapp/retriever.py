import os
import logging
import chromadb
from myapp.embed import embedding_model

# ✅ Setup ChromaDB persistent client
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="example_business_docs")
logging.info(f"ChromaDB collection ready: {collection.name}")

def retrieve(query, top_k=3):
    try:
        query_embedding = embedding_model.encode(query).tolist()
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k)

        if not results.get("documents") or not results["documents"][0]:
            logging.warning("⚠️ No documents retrieved from ChromaDB.")
            return ""

        docs = results["documents"][0]
        logging.debug(f"✅ Retrieved {len(docs)} documents: {docs}")

        combined = "\n---\n".join(docs)
        #if len(combined) > 1000:
         #   combined = combined[:1000].rsplit("\n", 1)[0] + "\n...[truncated]"

        return combined

    except Exception as e:
        logging.error(f"❌ Retrieval failed: {e}")
        return ""
