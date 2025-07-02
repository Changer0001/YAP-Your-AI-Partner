import os
import sys
import logging
import chromadb
import pytesseract
import fitz
from pdf2image import convert_from_path
from myapp.embed import embedding_model, chunk_text

# ✅ Logging setup
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# ✅ Ensure we can import from parent dir
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# ✅ Setup Chroma client
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="example_business_docs")

# ✅ Load .txt documents from the folder
def load_documents(folder_path):
    docs = []
    for filename in os.listdir(folder_path):
        full_path = os.path.join(folder_path, filename)
        try:
            if filename.endswith(".txt"):
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
            elif filename.endswith(".pdf"):
                logging.info(f"🔍 Found PDF: {filename}")
                content = load_pdf_text(full_path)
            else:
                continue  # Skip non-txt and non-pdf files
            if content:            
                        docs.append((filename, content))
                        logging.info(f"📄 Loaded: {filename}")
        except Exception as e:
                logging.warning(f"⚠️ Failed to read {filename}: {e}")
    return docs

def load_pdf_text(path):
    try:
        images = convert_from_path(path)
        text = ""
        for i, image in enumerate(images):
            ocr_result = pytesseract.image_to_string(image)
            text += ocr_result + "\n"
        return text.strip()
    except Exception as e:
        logging.error(f"❌ OCR failed on {path}: {e}")
        return ""
    
# ✅ Ingest documents by chunking and embedding
def ingest_and_store(docs):
    idx = 0
    for filename, text in docs:
        chunks = chunk_text(text)
        for chunk in chunks:
            try:
                if not chunk.strip():
                    continue
                embedding = embedding_model.encode(chunk).tolist()
                chunk_id = f"{filename}_{idx}"
                collection.add(documents=[chunk], embeddings=[embedding], ids=[chunk_id])
                logging.info(f"✅ Ingested: {chunk_id} | {chunk[:60]}...")
                idx += 1
            except Exception as e:
                logging.warning(f"⚠️ Failed to ingest chunk {chunk_id}: {e}")
    logging.info(f"📦 Total chunks added: {idx}")

# ✅ Main entry
if __name__ == "__main__":
    folder_path = "../data/example_business_docs" 
    if not os.path.exists(folder_path):
        logging.error(f"❌ Folder not found: {folder_path}")
        sys.exit(1)

    docs = load_documents(folder_path)
    if not docs:
        logging.warning("⚠️ No documents loaded.")
    else:
        ingest_and_store(docs)

