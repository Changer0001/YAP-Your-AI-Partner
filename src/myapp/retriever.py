# retriever.py
import os
import time
import logging
import chromadb
from myapp.chroma_config import client
from myapp.embed import embedding_model

CHROMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chroma_db"))

# ✅ Setup ChromaDB persistent client
collection = client.get_or_create_collection(name="example_business_docs")

# Load documents once at import
try:
    print("🔄 Starting ChromaDB doc fetch...")
    t0 = time.time()
    all_docs = collection.get(include=["documents"])
    raw_docs = all_docs.get("documents", [])
    print("✅ Raw ChromaDB fetch complete")

    print("🧪 raw_docs structure:", type(raw_docs), "len =", len(raw_docs))
    print(f"📦 Total docs in ChromaDB: {len(raw_docs)} (loaded in {time.time() - t0:.2f}s)")

    if raw_docs:
        print("🟢 ChromaDB contains data ✅")
    else:
        print("🔴 ChromaDB is EMPTY ❌")

except Exception as e:
    print("❌ Failed to load documents from ChromaDB:", e)
    raw_docs = []

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Score booster (position-based and heading-based)
def boost_retrieval_results(results):
    for i, metadata in enumerate(results["metadatas"][0]):
        score = results["distances"][0][i]

        if not isinstance(metadata, dict):
            logging.warning(f"⚠️ Missing metadata for doc {i}, skipping boost.")
            continue

        position = metadata.get("position", 100)
        heading = metadata.get("heading", "").lower()

        if position == 0:
            score -= 0.15
        if "introduction" in heading:
            score -= 0.1

        results["distances"][0][i] = score
    return results

# Main function
def retrieve(query, top_k=10):
    try:
        logging.info(f"🔍 Querying for: {query}")
        query_embedding = embedding_model.encode(query).tolist()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
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

        # ✅ Filter out too-short or broken chunks
        docs = [doc.strip() for doc, _ in sorted_docs if doc and len(doc.strip()) > 50]

        if not docs:
            logging.warning("⚠️ Retrieved docs were empty or too short.")
            return ""

        logging.info(f"✅ Final cleaned documents count: {len(docs)}")
        for i, doc in enumerate(docs):
            logging.info(f"📄 Clean Doc {i+1}: {doc[:80]}...")

        return "\n---\n".join(docs)

    except Exception as e:
        logging.error(f"❌ Retrieval failed: {e}")
        return ""


# Test run
if __name__ == "__main__":
    query = "What is our refund policy?"
    retrieved = retrieve(query)
    print("🔍 Retrieved document chunks:")
    print(retrieved if retrieved else "❌ No relevant documents retrieved.")
