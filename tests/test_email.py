"""Tests for POST /api/send-email."""
from unittest.mock import MagicMock, patch

import pytest


def _resend_patch(side_effect=None):
    """Return a context manager that stubs resend.Emails.send."""
    mock_send = MagicMock(side_effect=side_effect)
    return patch("web.main.resend.Emails.send", mock_send), mock_send


@pytest.mark.asyncio
async def test_send_email_missing_resend_config(client, fake_mp4, monkeypatch):
    """Missing RESEND env vars → 500."""
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("RESEND_FROM", raising=False)

    resp = await client.post(
        "/api/send-email",
        json={"to": "dest@example.com", "filename": fake_mp4.name},
    )
    assert resp.status_code == 500
    assert "Resend" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_send_email_video_not_found(client, monkeypatch):
    """Video file does not exist → 404."""
    monkeypatch.setenv("RESEND_API_KEY", "re_test123")
    monkeypatch.setenv("RESEND_FROM", "noreply@example.com")

    resp = await client.post(
        "/api/send-email",
        json={"to": "dest@example.com", "filename": "ghost.mp4"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename",
    [
        "../config.json",
        "../../etc/passwd",
        "subdir/../../../etc/passwd",
    ],
)
async def test_send_email_path_traversal_rejected(client, monkeypatch, filename):
    """Path traversal in filename → 400."""
    monkeypatch.setenv("RESEND_API_KEY", "re_test123")
    monkeypatch.setenv("RESEND_FROM", "noreply@example.com")

    resp = await client.post(
        "/api/send-email",
        json={"to": "dest@example.com", "filename": filename},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_send_email_success(client, fake_mp4, monkeypatch):
    """Happy path: Resend called, returns ok."""
    monkeypatch.setenv("RESEND_API_KEY", "re_test123")
    monkeypatch.setenv("RESEND_FROM", "noreply@example.com")

    ctx, mock_send = _resend_patch()
    with ctx:
        resp = await client.post(
            "/api/send-email",
            json={"to": "dest@example.com", "filename": fake_mp4.name},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[0][0]
    assert call_kwargs["to"] == ["dest@example.com"]
    assert call_kwargs["attachments"][0]["filename"] == fake_mp4.name


@pytest.mark.asyncio
async def test_send_email_resend_exception_propagated(client, fake_mp4, monkeypatch):
    """If Resend SDK raises, the endpoint returns 500."""
    monkeypatch.setenv("RESEND_API_KEY", "re_test123")
    monkeypatch.setenv("RESEND_FROM", "noreply@example.com")

    ctx, _ = _resend_patch(side_effect=RuntimeError("network timeout"))
    with ctx:
        resp = await client.post(
            "/api/send-email",
            json={"to": "dest@example.com", "filename": fake_mp4.name},
        )

    assert resp.status_code == 500
    assert "network timeout" in resp.json()["detail"]
