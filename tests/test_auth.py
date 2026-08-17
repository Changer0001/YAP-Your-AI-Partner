"""Auth tests — password hashing and signed session tokens (no server needed)."""
import time

from backend.services import auth


def test_password_hash_roundtrip():
    salt, h = auth.hash_password("correct horse battery staple")
    assert auth.verify_password("correct horse battery staple", salt, h)
    assert not auth.verify_password("wrong password", salt, h)


def test_password_salts_differ():
    s1, h1 = auth.hash_password("same")
    s2, h2 = auth.hash_password("same")
    assert s1 != s2 and h1 != h2  # random salt per hash


def test_token_sign_and_verify():
    tok = auth.sign_token({"sub": "burak", "role": "admin"})
    claims = auth.verify_token(tok)
    assert claims["sub"] == "burak" and claims["role"] == "admin"


def test_token_expired():
    tok = auth.sign_token({"sub": "x"}, ttl=-1)
    assert auth.verify_token(tok) is None


def test_token_tampered():
    tok = auth.sign_token({"sub": "x"})
    assert auth.verify_token(tok + "x") is None
    assert auth.verify_token("not.a.token") is None
