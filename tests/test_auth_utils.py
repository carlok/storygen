"""Unit tests for auth helper functions (no HTTP, no DB)."""
import pytest


def test_make_and_read_session_cookie_roundtrip():
    """make_session_cookie → read_session_cookie returns the same user_id."""
    from auth import make_session_cookie, read_session_cookie

    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = make_session_cookie(user_id)

    assert isinstance(token, str)
    assert len(token) > 0

    recovered = read_session_cookie(token)
    assert recovered == user_id


def test_read_session_cookie_invalid_returns_none():
    """Garbage token → read_session_cookie returns None (BadSignature)."""
    from auth import read_session_cookie

    assert read_session_cookie("not-a-valid-token") is None


def test_read_session_cookie_empty_returns_none():
    """Empty string → read_session_cookie returns None."""
    from auth import read_session_cookie

    assert read_session_cookie("") is None
