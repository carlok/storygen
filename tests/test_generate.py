"""Tests for POST /api/generate."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web.main import _smtp_send


_BASE_UPDATE = {
    "index": 0,
    "text": "Updated scene 1",
    "align_center": False,
    "center_x": False,
    "bw": False,
    "fade_in": True,
    "fade_out": False,
    "text_position": [100, 900],
}

# Patch the background task to a no-op so tests never touch the real DB
# or run subprocess. Tests that need to inspect the bg task args use their own patch.
_NO_BG = patch("web.main._run_generate_and_email", new_callable=AsyncMock)


@pytest.fixture(autouse=True)
def smtp_env(monkeypatch):
    """Set minimum SMTP env vars so the preflight check passes in every test.
    Individual tests that want to test the missing-SMTP case override these."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")


@pytest.mark.asyncio
async def test_generate_success(client):
    """Happy path: job queued immediately, response is {status: queued}."""
    with _NO_BG:
        resp = await client.post("/api/generate", json=[_BASE_UPDATE])
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    # No filename in the response — video is delivered via email
    assert "filename" not in resp.json()


@pytest.mark.asyncio
async def test_generate_updates_config(client, mock_db_session):
    """POST /api/generate persists block changes to the DB."""
    _, session = mock_db_session
    payload = [
        {
            "index": 1,
            "text": "Brand new caption",
            "align_center": True,
            "center_x": False,
            "bw": True,
            "fade_in": False,
            "fade_out": True,
            "text_position": [50, 800],
        }
    ]
    with _NO_BG:
        resp = await client.post("/api/generate", json=payload)
    assert resp.status_code == 200
    # At minimum: one commit for config update, one for pending Job
    assert session.commit.call_count >= 2


@pytest.mark.asyncio
async def test_generate_invalid_block_index(client):
    """Block index out of range → 400."""
    payload = [
        {
            "index": 99,
            "text": "oops",
            "align_center": False,
            "center_x": False,
            "bw": False,
            "fade_in": False,
            "fade_out": False,
            "text_position": [0, 0],
        }
    ]
    resp = await client.post("/api/generate", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_generate_smtp_preflight_fails(client, monkeypatch):
    """Missing SMTP config → 500 before any DB writes or queuing."""
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    resp = await client.post("/api/generate", json=[_BASE_UPDATE])
    assert resp.status_code == 500
    assert "Email delivery" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_sanitizes_output_prefix(client, config_file):
    """Dangerous characters in output_prefix are stripped before passing to bg task."""
    config = json.loads(config_file.read_text())
    config["output_prefix"] = "../../../etc/passwd"
    config_file.write_text(json.dumps(config))

    with patch("web.main._run_generate_and_email", new_callable=AsyncMock) as mock_bg:
        resp = await client.post("/api/generate", json=[_BASE_UPDATE])

    assert resp.status_code == 200
    # Filename is the 3rd positional arg: (user_id, user_email, filename, tmp_path, job_id)
    called_filename = mock_bg.call_args[0][2]
    assert ".." not in called_filename
    assert "/" not in called_filename
    prefix = called_filename.split("_20")[0]
    assert all(c.isalnum() or c in "-_" for c in prefix)


@pytest.mark.asyncio
async def test_generate_daily_limit_429(client, mock_db_session):
    """Daily video limit reached → 429."""
    _, session = mock_db_session
    high_count = MagicMock()
    high_count.scalar_one.return_value = 99
    session.execute = AsyncMock(return_value=high_count)

    resp = await client.post("/api/generate", json=[_BASE_UPDATE])
    assert resp.status_code == 429
    assert "Daily limit" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_creates_job_record(client, mock_db_session):
    """Generate inserts a Job with status='pending' at request time."""
    _, session = mock_db_session
    with _NO_BG:
        resp = await client.post("/api/generate", json=[_BASE_UPDATE])
    assert resp.status_code == 200

    from db.models import Job
    job_adds = [c for c in session.add.call_args_list if isinstance(c[0][0], Job)]
    assert len(job_adds) == 1
    assert job_adds[0][0][0].status == "pending"
    assert job_adds[0][0][0].filename.endswith(".mp4")


def test_smtp_send_skips_starttls_when_server_does_not_advertise_it(monkeypatch):
    """Local SMTP catchers such as Mailpit should work without STARTTLS support."""
    calls = {"ehlo": 0, "sent": False}

    class FakeSMTP:
        def __init__(self, host, port):
            assert host == "localhost"
            assert port == 1025

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def ehlo(self):
            calls["ehlo"] += 1

        def has_extn(self, name):
            assert name == "starttls"
            return False

        def starttls(self):
            raise AssertionError("STARTTLS should not be used when unsupported")

        def login(self, user, password):
            raise AssertionError("login should not run without credentials")

        def send_message(self, msg):
            calls["sent"] = True
            assert msg["To"] == "user@example.com"

    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setattr("web.main.smtplib.SMTP", FakeSMTP)

    _smtp_send("user@example.com", "Subject", "Body")

    assert calls == {"ehlo": 1, "sent": True}


def test_smtp_send_uses_starttls_when_server_advertises_it(monkeypatch):
    """SMTP providers that advertise STARTTLS should still get an encrypted session."""
    calls = {"ehlo": 0, "starttls": 0, "login": 0, "sent": False}

    class FakeSMTP:
        def __init__(self, host, port):
            assert host == "smtp.example.com"
            assert port == 587

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def ehlo(self):
            calls["ehlo"] += 1

        def has_extn(self, name):
            assert name == "starttls"
            return True

        def starttls(self):
            calls["starttls"] += 1

        def login(self, user, password):
            calls["login"] += 1
            assert (user, password) == ("smtp-user", "smtp-pass")

        def send_message(self, msg):
            calls["sent"] = True
            assert msg["Subject"] == "Subject"

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.setenv("SMTP_USER", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-pass")
    monkeypatch.setattr("web.main.smtplib.SMTP", FakeSMTP)

    _smtp_send("user@example.com", "Subject", "Body")

    assert calls == {"ehlo": 2, "starttls": 1, "login": 1, "sent": True}
