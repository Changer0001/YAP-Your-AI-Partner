"""Intent router tests — conversational messages must not trigger RAG."""
from backend.services.intent import KNOWLEDGE, classify


def test_greeting():
    assert classify("hello").type == "greeting"
    assert classify("Good morning").type == "greeting"


def test_identity_over_greeting():
    # "hi, who are you?" should resolve to identity, not greeting
    assert classify("hi, who are you?").type == "identity"
    assert classify("who is your owner?").type == "identity"


def test_capabilities():
    assert classify("what can you do?").type == "capabilities"


def test_knowledge_query_passthrough():
    i = classify("What VLAN is used for POS at Property A?")
    assert i.type == KNOWLEDGE
    assert i.response is None


def test_identity_response_is_deterministic():
    r = classify("who are you").response
    assert "IT Copilot" in r  # from config, not from documents
