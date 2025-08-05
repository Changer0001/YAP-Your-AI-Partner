from llm.llm_interface import ask_llm_hf
from retriever.retriever import retrieve

# Define query
query = "What is our refund policy?"

# Retrieve top document chunks from ChromaDB
doc_context = retrieve(query, top_k=5)

# ✅ Preview first 300 characters of the context to confirm it's relevant
print("🔍 Retrieved Context Preview:")
print(doc_context[:300] if doc_context else "❌ No context found.")

# Ask the LLM with retrieved context
answer = ask_llm_hf(
    question=query,
    history_blocks=[],
    doc_context=doc_context
)

# Show final answer
print("\n🤖 Final Answer:\n", answer)
