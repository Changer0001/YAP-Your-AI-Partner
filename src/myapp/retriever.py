import os
import logging
import chromadb
from myapp.embed import embedding_model





# ✅ Setup ChromaDB persistent client
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="example_business_docs")

all_docs = collection.get(include=["documents"])
print(f"📦 Total docs in ChromaDB: {len(all_docs['documents'])}")


if len(all_docs['documents']) > 0:
    print("🟢 ChromaDB contains data ✅")
else:
    print("🔴 ChromaDB is EMPTY ❌")

logging.basicConfig(level=logging.DEBUG)  # Ensure debug logs show

def retrieve(query, top_k=10):
    try:
        logging.info(f"🔍 Querying for: {query}")
        query_embedding = embedding_model.encode(query).tolist()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents"]
        )

        logging.debug(f"🔍 Raw Chroma results: {results}")

        if not results.get("documents") or not results["documents"][0]:
            logging.warning("⚠️ No documents retrieved from ChromaDB.")
            return ""

        docs = results["documents"][0]
        logging.info(f"✅ Retrieved {len(docs)} documents:")
        for i, doc in enumerate(docs):
            logging.info(f"📄 Doc {i+1}: {doc[:80]}...")  # Only show preview

        return "\n---\n".join(docs)

    except Exception as e:
        logging.error(f"❌ Retrieval failed: {e}")
        return ""
