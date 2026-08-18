"""Web fetch: HTML text extraction + SSRF guardrails (no network needed for these cases)."""
import pytest

from backend.services import webfetch


def test_html_extraction_strips_scripts_and_gets_title():
    p = webfetch._TextExtractor()
    p.feed("<html><head><title>Switch Guide</title><style>.x{}</style></head>"
           "<body><h1>VLAN 55</h1><script>alert(1)</script><p>POS uses VLAN 55.</p></body></html>")
    assert p.title == "Switch Guide"
    text = "\n".join(p.parts)
    assert "VLAN 55" in text and "POS uses VLAN 55." in text
    assert "alert" not in text  # script content dropped


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com/x", "javascript:alert(1)",
])
def test_reject_bad_scheme(url):
    with pytest.raises(ValueError):
        webfetch.fetch_url(url)


@pytest.mark.parametrize("url", [
    "http://localhost/x", "http://127.0.0.1/x", "http://169.254.169.254/latest",
    "http://192.168.1.1/", "http://10.0.0.5/",
])
def test_block_internal_hosts(url):
    with pytest.raises(ValueError):
        webfetch.fetch_url(url)
