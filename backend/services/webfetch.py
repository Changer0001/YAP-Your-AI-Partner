"""Fetch and extract text from a public web page — legitimate ingestion of docs you can view.

Guardrails:
- only http/https, and only PUBLIC hosts (private/loopback/link-local/reserved IPs are blocked,
  preventing server-side request forgery against internal systems);
- redirects are NOT followed automatically (a redirect returns an error asking for the final URL),
  so a public URL can't bounce to an internal one;
- response size and time are capped.

Standard library only.
"""
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = 15


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # block automatic redirects (SSRF hardening)


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.title: str | None = None
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = data.strip() or None
        if self._skip:
            return
        text = data.strip()
        if text:
            self.parts.append(text)


def _host_is_public(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def fetch_url(url: str) -> dict:
    """Return {title, text, url} for a public web page. Raises ValueError with a clear message."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Only http:// and https:// URLs are allowed")
    if not _host_is_public(parsed.hostname):
        raise ValueError("That address is blocked (internal/private hosts are not allowed)")

    opener = build_opener(_NoRedirect)
    req = Request(url, headers={"User-Agent": "YAP/1.0 (+local knowledge base)"})
    try:
        resp = opener.open(req, timeout=TIMEOUT)
    except HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308):
            raise ValueError("The URL redirects — open it in a browser and paste the final URL")
        raise ValueError(f"Could not fetch the page (HTTP {exc.code})")
    except (URLError, socket.timeout) as exc:
        raise ValueError(f"Could not reach the page: {exc}")

    ctype = (resp.headers.get("Content-Type") or "").lower()
    raw = resp.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Page is too large to ingest")
    body = raw.decode("utf-8", "ignore")

    if "html" in ctype or ctype.startswith("text/") or not ctype:
        parser = _TextExtractor()
        parser.feed(body)
        title = parser.title or parsed.hostname
        text = "\n".join(parser.parts)
    else:
        raise ValueError(f"Unsupported content type for a web page: {ctype or 'unknown'}")

    if len(text.strip()) < 20:
        raise ValueError("No readable text found on that page")
    return {"title": title, "text": text, "url": url.strip()}
