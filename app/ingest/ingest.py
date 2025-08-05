# myapp/ingest.py

import os
import sys
import logging
import chromadb
import pytesseract
import uuid
import hashlib
from pdf2image import convert_from_path
from retriever.embed import embedding_model, chunk_text
from core.chroma_config import client

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

collection = client.get_or_create_collection(name="example_business_docs")

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
                continue
            if content:
                docs.append((filename, content))
                logging.info(f"📄 Loaded: {filename}")
        except Exception as e:
            logging.warning(f"⚠️ Failed to read {filename}: {e}")
    return docs

def load_pdf_text(path):
    try:
        images = convert_from_path(path, first_page=1, last_page=5)
        text = ""
        for image in images:
            text += pytesseract.image_to_string(image) + "\n"
        return text.strip()
    except Exception as e:
        logging.error(f"❌ OCR failed on {path}: {e}")
        return ""

def ingest_and_store(docs):
    idx = 0
    seen_hashes = set()
    for filename, text in docs:
        chunks = chunk_text(text, filename=filename)
        logging.info(f"✂️ {filename} → {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            try:
                content = chunk["content"]
                metadata = chunk["metadata"]

                if not content.strip():
                    continue

                chunk_hash = hashlib.md5(content.encode()).hexdigest()
                if chunk_hash in seen_hashes:
                    logging.info(f"⏩ Skipped duplicate chunk in {filename}_{i}")
                    continue
                seen_hashes.add(chunk_hash)

                chunk_id = f"{filename}_{i}_{uuid.uuid4().hex[:8]}"
                embedding = embedding_model.encode(content).tolist()

                collection.add(
                    documents=[content],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    ids=[chunk_id]
                )
                logging.info(f"✅ Ingested: {chunk_id} | {content[:60]}...")
                idx += 1
            except Exception as e:
                logging.warning(f"⚠️ Failed to ingest chunk {filename}_{i}: {e}")
    logging.info(f"📦 Total chunks added: {idx}")
    logging.info(f"📚 Collection count after ingest: {collection.count()}")

if __name__ == "__main__":
    folder_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "example_business_docs"))
    if not os.path.exists(folder_path):
        logging.error(f"❌ Folder not found: {folder_path}")
        sys.exit(1)

    docs = load_documents(folder_path)
    if not docs:
        logging.warning("⚠️ No documents loaded.")
    else:
        ingest_and_store(docs)
