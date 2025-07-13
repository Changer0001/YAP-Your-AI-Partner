import os
import logging
import chromadb
from myapp.embed import embedding_model

CHROMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
client = chromadb.PersistentClient(path=CHROMA_PATH)



# ✅ Setup ChromaDB persistent client
collection = client.get_or_create_collection(name="example_business_docs")

all_docs = collection.get(include=["documents"])
print(f"📦 Total docs in ChromaDB: {len(all_docs['documents'])}")


if len(all_docs['documents']) > 0:
    print("🟢 ChromaDB contains data ✅")
else:
    print("🔴 ChromaDB is EMPTY ❌")

logging.basicConfig(level=logging.DEBUG)  # Ensure debug logs show

def boost_retrieval_results(results):
    for i, metadata in enumerate(results["metadatas"][0]):
        score = results["distances"][0][i]

        if not isinstance(metadata, dict):
            logging.warning(f"⚠️ Missing metadata for document {i}, skipping boost.")
            continue

        position = metadata.get("position", 100)
        heading = metadata.get("heading", "").lower()

        if position == 0:
            score -= 0.15
        if "introduction" in heading:
            score -= 0.1

        results["distances"][0][i] = score

    return results


def retrieve(query, top_k=10):
    try:
        logging.info(f"🔍 Querying for: {query}")
        query_embedding = embedding_model.encode(query).tolist()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas","distances"] 
        )

        logging.debug(f"🔍 Raw Chroma results: {results}")

        if not results.get("documents") or not results["documents"][0]:
            logging.warning("⚠️ No documents retrieved from ChromaDB.")
            return ""
        
         # Apply custom boosting
        results = boost_retrieval_results(results)

        # Sort results after boosting
        sorted_docs = sorted(
            zip(results["documents"][0], results["distances"][0]),
            key=lambda x: x[1]
        )

        docs = [doc for doc, _ in sorted_docs]
        logging.info(f"✅ Retrieved {len(docs)} documents:")
        for i, doc in enumerate(docs):
            logging.info(f"📄 Doc {i+1}: {doc[:80]}...")  # Only show preview

        return "\n---\n".join(docs)

    except Exception as e:
        logging.error(f"❌ Retrieval failed: {e}")
        return ""
