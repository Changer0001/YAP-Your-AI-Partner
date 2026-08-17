"""Tests for document parsing/chunking that need no external services."""
from pathlib import Path

from backend.services.documents import chunk_segments, _parse_text, parse_file


def test_chunk_overlap_and_metadata():
    segs = [{"text": " ".join(str(i) for i in range(100)), "page": 3, "section": "Intro"}]
    chunks = chunk_segments(segs, size=40, overlap=10)
    assert len(chunks) >= 3
    assert all(c["page"] == 3 and c["section"] == "Intro" for c in chunks)
    # overlap: consecutive chunks should share tokens
    first_words = chunks[0]["text"].split()
    second_words = chunks[1]["text"].split()
    assert set(first_words) & set(second_words)


def test_chunk_empty_segment():
    assert chunk_segments([{"text": "   ", "page": None, "section": None}], 40, 10) == []


def test_parse_text(tmp_path: Path):
    f = tmp_path / "note.txt"
    f.write_text("VLAN 55 is the POS VLAN at Property A.")
    segs = _parse_text(f)
    assert len(segs) == 1
    assert "VLAN 55" in segs[0]["text"]


def test_parse_markdown_dispatch(tmp_path: Path):
    f = tmp_path / "sop.md"
    f.write_text("# SOP\nCheck the switch port.")
    segs = parse_file(f)
    assert segs and "switch port" in segs[0]["text"]


def test_unsupported_extension(tmp_path: Path):
    f = tmp_path / "x.zip"
    f.write_bytes(b"x")
    try:
        parse_file(f)
        assert False, "should have raised"
    except ValueError:
        pass
