"""Local embeddings via Ollama (nomic-embed-text by default).

Runs entirely on the local machine; no document text ever leaves the host.
"""
from functools import lru_cache

from backend.config import settings


@lru_cache(maxsize=1)
def _client():
    from ollama import Client

    return Client(host=settings.ollama_host)


def embed_text(text: str) -> list[float]:
    resp = _client().embeddings(model=settings.embed_model, prompt=text)
    return resp["embedding"]


def embed_batch(texts: list[str]) -> list[list[float]]:
    return [embed_text(t) for t in texts]
