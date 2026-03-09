"""Tests for POST /api/generate."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_proc(returncode=0, stdout="", stderr=""):
    p = MagicMock()
    p.returncode = returncode
    p.stdout = stdout
    p.stderr = stderr
    return p


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


@pytest.mark.asyncio
async def test_generate_success(client, config_file):
    """Happy path: subprocess succeeds, filename returned."""
    payload = [_BASE_UPDATE]
    with patch("web.main.subprocess.run", return_value=_make_proc(0)) as mock_run:
        resp = await client.post("/api/generate", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["filename"].endswith(".mp4")
    assert data["filename"].startswith("testvid_")
    mock_run.assert_called_once()


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
    with patch("web.main.subprocess.run", return_value=_make_proc(0)):
        resp = await client.post("/api/generate", json=payload)

    assert resp.status_code == 200
    # At minimum: one commit for the config update and one for the job record
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
async def test_generate_subprocess_failure(client):
    """Subprocess non-zero exit → 500 with generic message."""
    payload = [
        {
            "index": 0,
            "text": "x",
            "align_center": False,
            "center_x": False,
            "bw": False,
            "fade_in": False,
            "fade_out": False,
            "text_position": [0, 0],
        }
    ]
    with patch(
        "web.main.subprocess.run",
        return_value=_make_proc(returncode=1, stderr="ffmpeg error"),
    ):
        resp = await client.post("/api/generate", json=payload)

    assert resp.status_code == 500
    assert "Video generation failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_sanitizes_output_prefix(client, config_file):
    """Dangerous characters in output_prefix are stripped."""
    # Write malicious prefix to config_file (used as template via _read_template)
    config = json.loads(config_file.read_text())
    config["output_prefix"] = "../../../etc/passwd"
    config_file.write_text(json.dumps(config))

    payload = [_BASE_UPDATE]
    with patch("web.main.subprocess.run", return_value=_make_proc(0)) as mock_run:
        resp = await client.post("/api/generate", json=payload)

    assert resp.status_code == 200
    filename = resp.json()["filename"]
    assert ".." not in filename
    assert "/" not in filename
    # The prefix should only contain safe chars
    prefix = filename.split("_20")[0]
    assert all(c.isalnum() or c in "-_" for c in prefix)

    # The subprocess must have received the sanitized filename as second-to-last arg:
    # ["python", script_path, filename, tmp_config_path]
    called_args = mock_run.call_args[0][0]  # positional args list
    filename_arg = called_args[-2]           # filename is second-to-last
    assert ".." not in filename_arg
    assert "/" not in filename_arg


@pytest.mark.asyncio
async def test_generate_daily_limit_429(client, mock_db_session):
    """Daily video limit reached → 429."""
    _, session = mock_db_session

    # Make execute() return a count above the default limit (3)
    high_count = MagicMock()
    high_count.scalar_one.return_value = 99
    session.execute = AsyncMock(return_value=high_count)

    payload = [_BASE_UPDATE]
    resp = await client.post("/api/generate", json=payload)

    assert resp.status_code == 429
    assert "Daily limit" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_creates_job_record(client, mock_db_session):
    """Successful generate creates a Job record via session.add."""
    _, session = mock_db_session

    payload = [_BASE_UPDATE]
    with patch("web.main.subprocess.run", return_value=_make_proc(0)):
        resp = await client.post("/api/generate", json=payload)

    assert resp.status_code == 200

    # Verify a Job was added to the session
    from db.models import Job
    add_calls = session.add.call_args_list
    job_adds = [c for c in add_calls if isinstance(c[0][0], Job)]
    assert len(job_adds) == 1
    assert job_adds[0][0][0].status == "done"
    assert job_adds[0][0][0].filename.endswith(".mp4")


@pytest.mark.asyncio
async def test_generate_failed_job_still_recorded(client, mock_db_session):
    """Failed generate still creates a Job record with status 'failed'."""
    _, session = mock_db_session

    payload = [_BASE_UPDATE]
    with patch(
        "web.main.subprocess.run",
        return_value=_make_proc(returncode=1, stderr="some error"),
    ):
        resp = await client.post("/api/generate", json=payload)

    assert resp.status_code == 500

    from db.models import Job
    add_calls = session.add.call_args_list
    job_adds = [c for c in add_calls if isinstance(c[0][0], Job)]
    assert len(job_adds) == 1
    assert job_adds[0][0][0].status == "failed"
