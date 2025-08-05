import os
import re
from sentence_transformers import SentenceTransformer

# ✅ Load the sentence embedding model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def chunk_text(text: str, max_tokens: int = 300, filename: str = "unknown.txt") -> list:
    """
    Split text into chunks with approximately max_tokens words per chunk.
    Adds metadata for retrieval ranking (filename, position, heading).

    Args:
        text (str): Raw document text.
        max_tokens (int): Target max word count per chunk.
        filename (str): Source file name used in metadata.

    Returns:
        List[dict]: Each dict has "content" and "metadata" keys.
    """
    # Clean and split by sentence boundaries
    text = text.strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        words = sentence.split()
        if current_length + len(words) > max_tokens:
            if current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append(chunk_text)
            current_chunk = [sentence]
            current_length = len(words)
        else:
            current_chunk.append(sentence)
            current_length += len(words)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    # Build chunks with metadata
    chunk_data = []
    for idx, chunk in enumerate(chunks):
        chunk_data.append({
            "content": chunk,
            "metadata": {
                "filename": filename,
                "position": idx,
                "heading": detect_heading(chunk)  # Optional, see below
            }
        })

    return chunk_data

def detect_heading(text: str) -> str:
    """
    Optional helper to extract a heading-like line from the beginning of a chunk.
    """
    first_line = text.strip().split("\n", 1)[0]
    if len(first_line.split()) <= 10:  # likely a heading if short
        return first_line.strip()
    return ""
