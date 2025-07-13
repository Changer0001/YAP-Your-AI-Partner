from myapp.retriever import retrieve
import chromadb
import os
CHROMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "chroma_db"))
client = chromadb.PersistentClient(path=CHROMA_PATH)


if __name__ == "__main__":
    result = retrieve("What is the refund policy?")
    print("\n🧠 Retrieved Context:\n")
    print(result)
