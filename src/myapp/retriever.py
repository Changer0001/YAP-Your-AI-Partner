import os
import chromadb
import logging
from myapp.embed import embedding_model

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="example_business_docs")

def retrieve(query):
    query_embedding = embedding_model.encode(query).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=3)
    docs = results['documents'][0]
    logging.debug(f"Retrieved documents: {docs}")
    combined = "\n---\n".join(docs)
    if len(combined) > 1000:
        combined = combined[:1000] + "..."
    return combined
