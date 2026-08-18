"""Email parsing tests (no external tools needed for .eml)."""
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

from backend.services import email_ingest


def _msg():
    m = EmailMessage()
    m["From"] = "Alex <alex@example.com>"
    m["To"] = "net-team@example.com"
    m["Subject"] = "RE: Switch migration - Site X"
    m["Date"] = "Tue, 14 Jul 2026 16:30:00 -0700"
    m["Message-ID"] = "<abc123@example.com>"
    m["References"] = "<root@example.com> <mid@example.com>"
    m.set_content("Migration postponed to Tuesday. POS stays on VLAN 55.")
    return BytesParser(policy=policy.default).parsebytes(bytes(m))


def test_parse_message_fields():
    info = email_ingest.parse_message(_msg())
    assert info["subject"] == "RE: Switch migration - Site X"
    assert "alex@example.com" in info["from"]
    assert info["date"] == "2026-07-14"
    assert info["thread_root"] == "root@example.com"   # first Reference = thread root
    assert "VLAN 55" in info["body"]


def test_document_text_has_headers_and_body():
    text = email_ingest.build_document_text(email_ingest.parse_message(_msg()))
    assert text.startswith("From: Alex")
    assert "Subject: RE: Switch migration" in text
    assert "VLAN 55" in text


def test_html_only_email_is_stripped():
    m = EmailMessage()
    m["From"] = "x@y.com"; m["Subject"] = "HTML"; m["Date"] = "Tue, 14 Jul 2026 16:30:00 -0700"
    m.set_content("<html><body><p>VLAN <b>30</b> is active.</p></body></html>", subtype="html")
    info = email_ingest.parse_message(BytesParser(policy=policy.default).parsebytes(bytes(m)))
    assert "VLAN" in info["body"] and "<b>" not in info["body"]


def test_unsupported_extension(tmp_path):
    import pytest
    f = tmp_path / "x.zip"
    f.write_bytes(b"x")
    with pytest.raises(ValueError):
        list(email_ingest.iter_messages(f))
