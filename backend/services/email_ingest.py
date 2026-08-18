"""Parse exported Outlook/email files into normalized messages for local ingestion.

Supported (all things you can export yourself — no Graph API):
- .eml   single message (e.g. "Download" from Outlook on the web)
- .mbox  bulk mailbox export
- .pst   Outlook Data File (requires the `readpst` tool: sudo apt install pst-utils)

Each message keeps subject, sender, recipients, date, message-id, thread key, body text and
attachment names, so answers can cite the exact email and reason about chronology.
"""
import mailbox
import shutil
import subprocess
import tempfile
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Iterator

EMAIL_EXTENSIONS = {".eml", ".mbox", ".pst"}


def _strip_html(html: str) -> str:
    from backend.services.webfetch import _TextExtractor

    p = _TextExtractor()
    try:
        p.feed(html or "")
    except Exception:
        return html or ""
    return "\n".join(p.parts)


def parse_message(msg: EmailMessage) -> dict:
    subject = (msg.get("Subject") or "").strip() or "(no subject)"
    sender = (msg.get("From") or "").strip()
    to = ", ".join(a for _, a in getaddresses(msg.get_all("To", [])) if a)
    try:
        dt = parsedate_to_datetime(msg.get("Date"))
        date_iso = dt.date().isoformat() if dt else None
    except Exception:
        date_iso = None
    message_id = (msg.get("Message-ID") or "").strip()
    refs = (msg.get("References") or msg.get("In-Reply-To") or "").split()
    thread_root = (refs[0] if refs else message_id).strip("<> ")

    plain = html = None
    attachments: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                fn = part.get_filename()
                if fn:
                    attachments.append(fn)
                continue
            ctype = part.get_content_type()
            try:
                if ctype == "text/plain" and plain is None:
                    plain = part.get_content()
                elif ctype == "text/html" and html is None:
                    html = part.get_content()
            except Exception:
                continue
    else:
        try:
            content = msg.get_content()
        except Exception:
            content = ""
        if msg.get_content_type() == "text/html":
            html = content
        else:
            plain = content

    body = (plain if plain else _strip_html(html) if html else "").strip()
    return {"subject": subject, "from": sender, "to": to, "date": date_iso,
            "message_id": message_id, "thread_root": thread_root,
            "body": body, "attachments": attachments}


def iter_messages(path: Path) -> Iterator[EmailMessage]:
    ext = path.suffix.lower()
    parser = BytesParser(policy=policy.default)
    if ext == ".eml":
        with open(path, "rb") as f:
            yield parser.parse(f)
    elif ext == ".mbox":
        box = mailbox.mbox(str(path))
        for m in box:
            yield parser.parsebytes(m.as_bytes())
    elif ext == ".pst":
        if not shutil.which("readpst"):
            raise ValueError("PST support needs the 'readpst' tool. Install it with: "
                             "sudo apt install pst-utils  (or export emails as .eml instead)")
        tmp = tempfile.mkdtemp(prefix="yap_pst_")
        try:
            subprocess.run(["readpst", "-e", "-o", tmp, str(path)],
                           check=True, capture_output=True, timeout=1800)
            for eml in sorted(Path(tmp).rglob("*.eml")):
                with open(eml, "rb") as f:
                    yield parser.parse(f)
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"readpst failed: {exc.stderr.decode('utf-8', 'ignore')[:200]}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        raise ValueError(f"Unsupported email file type: {ext}")


def build_document_text(info: dict) -> str:
    """A searchable, citable text block: headers + body."""
    lines = [f"From: {info['from']}", f"To: {info['to']}", f"Date: {info['date'] or 'unknown'}",
             f"Subject: {info['subject']}"]
    if info["thread_root"]:
        lines.append(f"Thread: {info['thread_root']}")
    if info["attachments"]:
        lines.append("Attachments: " + ", ".join(info["attachments"]))
    return "\n".join(lines) + "\n\n" + info["body"]
