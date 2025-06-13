import os
import re
import logging
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from transformers import logging as hf_logging
from huggingface_hub import login

# ✅ Configure logging to file
logging.basicConfig(
    filename="app.log",
    filemode="a",  # 'w' to overwrite, 'a' to append
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG
)

# ✅ Silence most Hugging Face warnings
hf_logging.set_verbosity_error()

# 📌 Load environment variables (API keys, tokens)
load_dotenv()

# ✅ Initialize OpenAI
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ Initialize Hugging Face
login(token=os.getenv("HF_API_TOKEN"))
hf_model_id = "microsoft/phi-2"
hf_tokenizer = AutoTokenizer.from_pretrained(hf_model_id)
hf_tokenizer.pad_token = hf_tokenizer.eos_token  # Fix pad token warning
hf_model = AutoModelForCausalLM.from_pretrained(hf_model_id)
hf_pipe = pipeline(
    "text-generation",
    model=hf_model,
    tokenizer=hf_tokenizer,
    return_full_text=False,
    pad_token_id=hf_tokenizer.eos_token_id
)

# ✅ Initialize ChromaDB for document storage & search
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="example_business_docs")

# ✅ Load sentence-transformer model for embeddings
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# 📌 Helper: Chunk large text into smaller chunks (~300 tokens by words)
def chunk_text(text, max_tokens=300):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence_length = len(sentence.split())
        if current_length + sentence_length > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_length = sentence_length
        else:
            current_chunk.append(sentence)
            current_length += sentence_length

    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

# 📂 Ingest documents (text files)
def load_documents(folder_path):
    docs = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.endswith(".txt") and os.path.isfile(file_path):
            with open(file_path, 'r', encoding="utf-8") as f:
                docs.append(f.read())
    return docs

# 🔢 Embed documents & store them in ChromaDB with chunking
def ingest_and_store(docs):
    idx = 0
    for doc in docs:
        chunks = chunk_text(doc, max_tokens=300)
        for chunk in chunks:
            embedding = embedding_model.encode(chunk).tolist()
            collection.add(documents=[chunk], embeddings=[embedding], ids=[f"doc_{idx}"])
            idx += 1
    logging.info(f"Ingested {idx} chunks into ChromaDB.")

# 🔍 Retrieve relevant documents from ChromaDB
def retrieve(query):
    query_embedding = embedding_model.encode(query).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=3)
    docs = results['documents'][0]
    logging.debug(f"Retrieved documents: {docs}")
    combined = "\n---\n".join(docs)
    if len(combined) > 1000:
        combined = combined[:1000] + "..."
    return combined

# 🤖 Generate answer using OpenAI
def ask_llm_openai(question, context):
    prompt = f"""Answer the question based only on the information provided in the context below.
If the answer cannot be found in the context, say 'I don't know.'

Context:
{context}

Question:
{question}
Answer:
"""
    logging.debug(f"Prompt sent to OpenAI:\n{prompt}")
    response = client_openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for answering business questions."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
    )
    answer = response.choices[0].message.content.strip()
    logging.debug(f"Generated answer (OpenAI): {answer}")
    return answer

# 🤖 Generate answer using Hugging Face (phi-2)
def ask_llm_hf(question, context):
    prompt = f"""Answer the question based only on the information provided in the context below.
If the answer cannot be found in the context, say 'I don't know.'

Context:
{context}

Question:
{question}
Answer:
"""
    logging.debug(f"Prompt sent to HF model:\n{prompt}")
    response = hf_pipe(prompt, max_new_tokens=150, do_sample=True, temperature=0.7)
    answer = response[0]['generated_text'].strip()
    logging.debug(f"Generated answer (HF): {answer}")
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
            context = retrieve(question)

            if provider == 'h':
                answer = ask_llm_hf(question, context)
            else:
                answer = ask_llm_openai(question, context)

            print(f"\n💬 Answer: {answer}")

        except Exception as e:
            logging.error(f"Error during execution: {e}")
            print(f"⚠️ Error: {e}")
