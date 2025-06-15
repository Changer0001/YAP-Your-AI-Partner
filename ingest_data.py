
import os
import argparse
import logging
from myapp.ingest import load_documents, ingest_and_store
folder_path = "./data/example_business_docs"

documents = load_documents(folder_path)
ingest_and_store(documents)

print(f"Ingested {len(documents)} documents from: {folder_path}")



logging.basicConfig(level=logging.INFO)

def main(folder_path):
    if not os.path.isdir(folder_path):
        logging.error(f"❌ Folder does not exist: {folder_path}")
        return

    documents = load_documents(folder_path)
    if not documents:
        logging.warning("⚠️ No text files found in the specified folder.")
        return

    ingest_and_store(documents)
    logging.info(f"✅ Successfully ingested {len(documents)} documents from '{folder_path}'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into the local vector database.")
    parser.add_argument("folder_path", type=str, help="Path to the folder containing text files")

    args = parser.parse_args()
    main(args.folder_path)
