"""Security helpers: filename sanitisation, extension allow-list, upload limits.

The application never builds filesystem paths from user input — uploaded files
are stored under a generated UUID name — so path traversal is structurally
impossible. These helpers add defence in depth.
"""
import os
import re
from pathlib import Path

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".txt", ".md", ".markdown", ".csv",
                      ".cfg", ".conf", ".log", ".ini"}


def sanitize_filename(name: str) -> str:
    """Strip any directory components and unsafe characters from a filename."""
    name = os.path.basename(name or "")
    name = re.sub(r"[^A-Za-z0-9._ \-]", "_", name).strip()
    return name[:200] or "file"


def is_allowed_extension(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def extension_of(filename: str) -> str:
    return Path(filename).suffix.lower()
