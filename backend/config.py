"""Central configuration. All values overridable via environment / .env file.

Local-first: every default points at a local resource. Nothing here reaches an
external AI service.
"""
import os
from pathlib import Path

try:  # dotenv is optional so the module imports even before deps are installed
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

BASE_DIR = Path(__file__).resolve().parent.parent


def _get(name: str, default: str) -> str:
    return os.getenv(name, default)


class Settings:
    # --- Local AI (Ollama) ---
    ollama_host: str = _get("OLLAMA_HOST", "http://127.0.0.1:11434")
    chat_model: str = _get("CHAT_MODEL", "qwen2.5:3b")
    embed_model: str = _get("EMBED_MODEL", "nomic-embed-text")

    # --- Storage (all local) ---
    data_dir: Path = Path(_get("DATA_DIR", str(BASE_DIR / "data")))

    # --- Retrieval / RAG parameters (configurable) ---
    chunk_size: int = int(_get("CHUNK_SIZE", "250"))          # words per chunk
    chunk_overlap: int = int(_get("CHUNK_OVERLAP", "50"))     # words overlap
    top_k: int = int(_get("TOP_K", "5"))                      # chunks retrieved
    similarity_threshold: float = float(_get("SIMILARITY_THRESHOLD", "0.2"))
    max_context_chars: int = int(_get("MAX_CONTEXT_CHARS", "6000"))

    # --- Uploads / security ---
    max_upload_mb: int = int(_get("MAX_UPLOAD_MB", "25"))

    # --- Server ---
    host: str = _get("HOST", "127.0.0.1")
    port: int = int(_get("PORT", "8000"))

    # --- Assistant identity (from config, never from company documents) ---
    assistant_name: str = _get("ASSISTANT_NAME", "YAP")
    assistant_owner: str = _get("ASSISTANT_OWNER", "your IT team")
    org_name: str = _get("ORG_NAME", "")

    # --- Accounts ---
    # Invite-only by default: only admins create accounts. Set to true to allow self-registration.
    allow_registration: bool = _get("ALLOW_REGISTRATION", "false").lower() in ("1", "true", "yes")

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def import_dir(self) -> Path:
        return self.data_dir / "import"

    @property
    def registry_path(self) -> Path:
        return self.data_dir / "registry.sqlite3"


settings = Settings()

# Ensure local storage exists.
for _p in (settings.data_dir, settings.chroma_dir, settings.upload_dir, settings.import_dir):
    _p.mkdir(parents=True, exist_ok=True)
