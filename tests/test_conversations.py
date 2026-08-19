"""Conversation store — per-user isolation (mandatory) and basic behavior."""
import importlib

import pytest


@pytest.fixture()
def conv(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from backend import config as cfg
    importlib.reload(cfg)
    from backend.services import conversations
    importlib.reload(conversations)
    return conversations


def test_user_isolation(conv):
    a = conv.create("userA", "A's chat")
    conv.add_message(a["id"], "userA", "user", "secret A")
    # userB must not be able to see or touch userA's conversation
    assert conv.get(a["id"], "userB") is None
    assert conv.messages(a["id"], "userB") == []
    assert conv.rename(a["id"], "userB", "hacked") is False
    assert conv.delete(a["id"], "userB") is False
    assert conv.add_message(a["id"], "userB", "user", "intrude") is None
    # owner is intact and userB's list never includes A's conversation
    assert conv.get(a["id"], "userA")["title"] == "A's chat"
    assert len(conv.messages(a["id"], "userA")) == 1
    assert all(c["id"] != a["id"] for c in conv.list_for("userB"))


def test_search_isolated(conv):
    a = conv.create("userA")
    conv.add_message(a["id"], "userA", "user", "POS uses VLAN 55")
    assert conv.search("userA", "VLAN")           # owner finds it
    assert conv.search("userB", "VLAN") == []      # other user gets nothing


def test_messages_and_count(conv):
    c = conv.create("u")
    conv.add_message(c["id"], "u", "user", "hi")
    conv.add_message(c["id"], "u", "assistant", "hello")
    assert conv.message_count(c["id"], "u") == 2
    assert [m["role"] for m in conv.messages(c["id"], "u")] == ["user", "assistant"]
