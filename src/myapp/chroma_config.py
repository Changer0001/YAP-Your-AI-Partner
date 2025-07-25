import chromadb
import chromadb.config
import os

CHROMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chroma_store"))
settings = chromadb.config.Settings(anonymized_telemetry=False)
client = chromadb.PersistentClient(path=CHROMA_PATH, settings=settings)
# Add this to confirm which collections exist
print("📂 Available Chroma Collections:")
for col in client.list_collections():
    print(f" - {col.name}")


print("📁 ChromaDB is using path:", CHROMA_PATH)
