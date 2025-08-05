# retriever.py
import os
import time
import logging
import chromadb
from core.chroma_config import client
from retriever.embed import embedding_model
from core.smart_threshold import get_dynamic_threshold

CHROMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
collection = client.get_or_create_collection(name="example_business_docs")

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# 🔍 Initial ChromaDB Check
try:
    print("🔄 Starting ChromaDB doc fetch...")
    t0 = time.time()
    all_docs = collection.get(include=["documents"])
    raw_docs = all_docs.get("documents", [])
    print(f"📦 Total docs in ChromaDB: {len(raw_docs)} (loaded in {time.time() - t0:.2f}s)")
    if not raw_docs:
        print("🔴 ChromaDB is EMPTY ❌")
except Exception as e:
    print("❌ Failed to load documents from ChromaDB:", e)
    raw_docs = []

# 📈 Optional score booster
def boost_retrieval_results(results):
    for i, metadata in enumerate(results["metadatas"][0]):
        score = results["distances"][0][i]
        if not isinstance(metadata, dict):
            continue
        position = metadata.get("position", 100)
        heading = metadata.get("heading", "").lower()
        if position == 0:
            score -= 0.15
        if "introduction" in heading:
            score -= 0.1
        results["distances"][0][i] = score
    return results

# 🧠 Query boosting
def boost_query(query: str) -> str:
    if "refund" in query.lower():
        return query + " return cancel cancellation money-back"
    return query

# 🔍 Main retriever function
from core.smart_threshold import get_dynamic_threshold

# 🔍 Main retriever function
def retrieve(query, top_k=10):
    try:
        boosted_query = boost_query(query)
        logging.info(f"🔍 Querying for: {boosted_query}")

        query_embedding = embedding_model.encode(boosted_query).tolist()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        if not results.get("documents") or not results["documents"][0]:
            logging.warning("⚠️ No documents retrieved from ChromaDB.")
            return ""

        # Boost and sort
        results = boost_retrieval_results(results)
        sorted_docs = sorted(
            zip(results["documents"][0], results["distances"][0]),
            key=lambda x: x[1]
        )

        # 🔁 Use dynamic threshold
        threshold = get_dynamic_threshold(query)
        logging.info(f"📊 Using dynamic threshold: {threshold:.2f}")

        # Filter low-quality results
        docs = []
        for i, (doc, dist) in enumerate(sorted_docs):
            doc = doc.strip()
            if not doc or len(doc) < 50:
                continue
            if dist > threshold:
                logging.warning(f"🚫 Skipping doc {i+1} due to high distance: {dist:.2f}")
                continue
            if any(k in doc.lower() for k in ["refund", "return", "cancellation", "money-back"]):
                logging.info(f"✅ Chunk {i+1} contains refund-related terms:\n{doc[:120]}...")
            else:
                logging.info(f"ℹ️ Chunk {i+1} is general:\n{doc[:120]}...")
            docs.append(doc)

        if not docs:
            logging.warning("⚠️ No relevant documents after filtering.")
            return ""

        return docs  # ✅ List of clean paragraph strings


    except Exception as e:
        logging.error(f"❌ Retrieval failed: {e}")
        return ""



# Test run
if __name__ == "__main__":
    query = "What is our refund policy?"
    retrieved = retrieve(query)
    print("🔍 Retrieved document chunks:")
    print(retrieved if retrieved else "❌ No relevant documents retrieved.")
