"""Tests for POST /api/send-email."""
from unittest.mock import MagicMock, patch

import pytest


def _smtp_patch(send_side_effect=None):
    """Return (ctx, mock_smtp_cls) that stubs smtplib.SMTP as a context manager."""
    mock_smtp_cls = MagicMock()
    if send_side_effect is not None:
        smtp_instance = mock_smtp_cls.return_value.__enter__.return_value
        smtp_instance.send_message.side_effect = send_side_effect
    ctx = patch("web.main.smtplib.SMTP", mock_smtp_cls)
    return ctx, mock_smtp_cls


@pytest.mark.asyncio
async def test_send_email_missing_smtp_config(client, fake_mp4, monkeypatch):
    """Missing SMTP env vars → 500."""
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)

    resp = await client.post(
        "/api/send-email",
        json={"to": "user@test.com", "filename": fake_mp4.name},
    )
    assert resp.status_code == 500
    assert "SMTP" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_send_email_video_not_found(client, monkeypatch):
    """Video file does not exist → 404."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

    resp = await client.post(
        "/api/send-email",
        json={"to": "user@test.com", "filename": "ghost.mp4"},
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
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

    resp = await client.post(
        "/api/send-email",
        json={"to": "user@test.com", "filename": filename},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_send_email_success(client, fake_mp4, monkeypatch):
    """Happy path: SMTP is called, endpoint returns ok."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

    ctx, mock_smtp_cls = _smtp_patch()
    with ctx:
        resp = await client.post(
            "/api/send-email",
            json={"to": "user@test.com", "filename": fake_mp4.name},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    # SMTP was instantiated and send_message was called
    mock_smtp_cls.assert_called_once()
    smtp_srv = mock_smtp_cls.return_value.__enter__.return_value
    smtp_srv.starttls.assert_called_once()
    smtp_srv.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_smtp_exception_propagated(client, fake_mp4, monkeypatch):
    """If SMTP send raises, the endpoint returns 500."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

    ctx, _ = _smtp_patch(send_side_effect=RuntimeError("network timeout"))
    with ctx:
        resp = await client.post(
            "/api/send-email",
            json={"to": "user@test.com", "filename": fake_mp4.name},
        )

    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_send_email_to_other_user_rejected(client, fake_mp4, monkeypatch):
    """Sending to someone else's email is rejected (open-relay guard)."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

    resp = await client.post(
        "/api/send-email",
        json={"to": "other@attacker.com", "filename": fake_mp4.name},
    )
    assert resp.status_code == 403
    assert "own email" in resp.json()["detail"]
