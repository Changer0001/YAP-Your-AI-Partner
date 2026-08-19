"""Intent router tests — conversational/identity messages must not trigger RAG."""
from backend.services.intent import (CAPABILITIES, FOUNDER, GREETING, IDENTITY,
                                     KNOWLEDGE, MEANING, RECALL, classify)


def test_greeting():
    assert classify("hello").type == GREETING
    assert classify("Good morning").type == GREETING
    assert classify("hello").response  # deterministic reply present


def test_identity():
    assert classify("who are you?").type == IDENTITY
    assert "YAP" in classify("who are you?").response


def test_meaning():
    assert classify("what does YAP stand for?").type == MEANING
    assert "Your AI Partner" in classify("what does yap stand for").response


def test_founder():
    assert classify("who founded YAP?").type == FOUNDER
    assert classify("who created you?").type == FOUNDER
    assert classify("who is your owner?").type == FOUNDER
    assert "Burak" in classify("who founded YAP?").response


def test_capabilities():
    assert classify("what can you do?").type == CAPABILITIES


def test_recall():
    assert classify("what did we discuss yesterday?").type == RECALL
    assert classify("what IP did I give you earlier?").type == RECALL


def test_knowledge_passthrough():
    i = classify("What VLAN is used for POS at Property A?")
    assert i.type == KNOWLEDGE and i.response is None
