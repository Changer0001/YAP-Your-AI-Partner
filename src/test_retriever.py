from myapp.retriever import retrieve
import chromadb
import os
from myapp.llm_interface import ask_llm_hf

CHROMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "chroma_db"))
client = chromadb.PersistentClient(path=CHROMA_PATH)

if __name__ == "__main__":
    retrieved_context = retrieve("What is the refund policy?")
    print("\n🧠 Retrieved Context:\n")
    print(retrieved_context)

    answer = ask_llm_hf(
        question="What is the refund policy?",
        history_blocks="",
        doc_context=retrieved_context,
        user_id=123
    )

    print("\n💬 Answer from LLM:\n", answer)
