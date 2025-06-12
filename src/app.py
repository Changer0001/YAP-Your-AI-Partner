import os
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from huggingface_hub import login

# 📌 Load environment variables (API keys, tokens)
load_dotenv()

# ✅ Initialize OpenAI
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ Initialize Hugging Face
login(token=os.getenv("HF_API_TOKEN"))
hf_model_id = "microsoft/phi-2"
hf_tokenizer = AutoTokenizer.from_pretrained(hf_model_id)
hf_model = AutoModelForCausalLM.from_pretrained(hf_model_id)

# IMPORTANT: Add return_full_text=False to avoid prompt being repeated in output
hf_pipe = pipeline(
    "text-generation",
    model=hf_model,
    tokenizer=hf_tokenizer,
    return_full_text=False  # Return only generated text, not prompt + generated text
)

# ✅ Initialize ChromaDB for document storage & search
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="business_docs")

# ✅ Load sentence-transformer model for embeddings
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# 📂 Ingest documents (text files)
def load_documents(folder_path):
    docs = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.endswith(".txt") and os.path.isfile(file_path):
            with open(file_path, 'r', encoding="utf-8") as f:
                docs.append(f.read())
    return docs

# 🔢 Embed documents & store them in ChromaDB
def ingest_and_store(docs):
    for idx, doc in enumerate(docs):
        embedding = embedding_model.encode(doc).tolist()
        collection.add(documents=[doc], embeddings=[embedding], ids=[f"doc_{idx}"])

# 🔍 Retrieve relevant documents from ChromaDB
def retrieve(query):
    query_embedding = embedding_model.encode(query).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=3)
    return results['documents'][0]

# 🤖 Generate answer using OpenAI
def ask_llm_openai(question, context):
    prompt = f"""Answer the following question using the provided context:\n\nContext:\n{context}\n\nQuestion:\n{question}"""
    response = client_openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for answering business questions."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()

# 🤖 Generate answer using Hugging Face (phi-2)
def ask_llm_hf(question, context):
    prompt = f"Answer the question based on this context:\n{context}\n\nQuestion: {question}\nAnswer:"
    print(f"\n[DEBUG] Prompt sent to HF model:\n{prompt}\n")
    response = hf_pipe(prompt, max_new_tokens=300, do_sample=False)
    answer = response[0]['generated_text'].strip()
    print(f"[DEBUG] Generated answer:\n{answer}\n")
    return answer

# 🚀 Main Execution Flow
if __name__ == "__main__":
    DATA_DIR = "./data/example_business_docs"

    if not os.path.exists(DATA_DIR):
        raise FileNotFoundError(f"❗ Data folder not found: {DATA_DIR}")

    print("📂 Loading and indexing documents...")
    documents = load_documents(DATA_DIR)
    ingest_and_store(documents)
    print(f"✅ {len(documents)} documents indexed. Ready to answer questions!")

    while True:
        try:
            question = input("\n❓ Ask a question (or type 'exit'): ").strip()
            if question.lower() == "exit":
                print("👋 Exiting. Goodbye!")
                break

            provider = input("💻 Use OpenAI (o) or Hugging Face (h)? ").strip().lower()

            context = " ".join(retrieve(question))

            if provider == 'h':
                answer = ask_llm_hf(question, context)
            else:
                answer = ask_llm_openai(question, context)

            print(f"\n💬 Answer: {answer}")

        except Exception as e:
            print(f"⚠️ Error: {e}")
