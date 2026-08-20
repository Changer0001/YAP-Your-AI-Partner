"""Multi-format document parsing and chunking.

Parsers return a list of *segments*: {text, page, section}. Segments preserve
page numbers (PDF) and headings/sheets (DOCX/XLSX) so citations can point at a
precise location. Heavy libraries are imported lazily so this module (and its
chunking logic) can be imported/tested without them installed.

Add a new format by writing a `_parse_<ext>` function and wiring it in
`parse_file`.
"""
import csv
from pathlib import Path
from typing import Optional

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".txt", ".md", ".markdown", ".csv",
                        ".cfg", ".conf", ".log", ".ini", ".json"}


def parse_file(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _parse_pdf(path)
    if ext == ".docx":
        return _parse_docx(path)
    if ext == ".xlsx":
        return _parse_xlsx(path)
    if ext == ".csv":
        return _parse_csv(path)
    if ext == ".json":
        return _parse_json(path)
    if ext in (".txt", ".md", ".markdown", ".cfg", ".conf", ".log", ".ini"):
        return _parse_text(path)
    raise ValueError(f"Unsupported file type: {ext}")


def _parse_json(path: Path) -> list[dict]:
    """Flatten JSON into readable, searchable 'path: value' lines (records, configs, exports)."""
    import json

    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return _parse_text(path)  # not valid JSON -> index the raw text

    lines: list[str] = []

    def walk(prefix: str, obj) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(f"{prefix}.{k}" if prefix else str(k), v)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(f"{prefix}[{i}]", v)
        else:
            lines.append(f"{prefix}: {obj}" if prefix else str(obj))

    walk("", data)
    text = "\n".join(lines).strip()
    return [{"text": text, "page": None, "section": None}] if text else []


def _parse_pdf(path: Path) -> list[dict]:
    from pypdf import PdfReader

    segments = []
    for i, page in enumerate(PdfReader(str(path)).pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            segments.append({"text": text, "page": i, "section": None})
    return segments


def _parse_docx(path: Path) -> list[dict]:
    import docx

    document = docx.Document(str(path))
    segments: list[dict] = []
    section: Optional[str] = None
    buffer: list[str] = []

    def flush():
        nonlocal buffer
        if buffer:
            segments.append({"text": "\n".join(buffer), "page": None, "section": section})
            buffer = []

    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name if para.style else "") or ""
        if style.lower().startswith("heading"):
            flush()
            section = text
        else:
            buffer.append(text)
    flush()
    return segments


def _parse_xlsx(path: Path) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    segments = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            segments.append({"text": "\n".join(rows), "page": None, "section": ws.title})
    wb.close()
    return segments


def _parse_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        rows = [" | ".join(r) for r in csv.reader(f) if any(cell.strip() for cell in r)]
    return [{"text": "\n".join(rows), "page": None, "section": None}] if rows else []


def _parse_text(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    return [{"text": text, "page": None, "section": None}] if text else []


def chunk_segments(segments: list[dict], size: int, overlap: int) -> list[dict]:
    """Word-based chunking with overlap, preserving each segment's page/section."""
    step = max(1, size - overlap)
    chunks = []
    for seg in segments:
        words = seg["text"].split()
        if not words:
            continue
        i = 0
        while i < len(words):
            text = " ".join(words[i:i + size]).strip()
            if text:
                chunks.append({"text": text, "page": seg.get("page"),
                               "section": seg.get("section")})
            i += step
    return chunks
