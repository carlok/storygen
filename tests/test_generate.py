"""Tests for POST /api/generate."""
import json
from unittest.mock import MagicMock, patch

import pytest


def _make_proc(returncode=0, stdout="", stderr=""):
    p = MagicMock()
    p.returncode = returncode
    p.stdout = stdout
    p.stderr = stderr
    return p


@pytest.mark.asyncio
async def test_generate_success(client, config_file):
    """Happy path: subprocess succeeds, filename returned."""
    payload = [
        {
            "index": 0,
            "text": "Updated scene 1",
            "align_center": False,
            "center_x": False,
            "bw": False,
            "fade_in": True,
            "fade_out": False,
            "text_position": [100, 900],
        }
    ]
    with patch("web.main.subprocess.run", return_value=_make_proc(0)) as mock_run:
        resp = await client.post("/api/generate", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["filename"].endswith(".mp4")
    assert data["filename"].startswith("testvid_")
    mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_generate_updates_config(client, config_file):
    """POST /api/generate persists text changes to config.json."""
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
        await client.post("/api/generate", json=payload)

    saved = json.loads(config_file.read_text())
    block = saved["blocks"][1]
    assert block["text"] == "Brand new caption"
    assert block["bw"] is True
    assert block["align_center"] is True
    assert block["text_position"] == [50, 800]


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
    """Subprocess non-zero exit → 500."""
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
    assert "ffmpeg error" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_sanitizes_output_prefix(client, config_file):
    """Dangerous characters in output_prefix are stripped."""
    import json as _json

    config = _json.loads(config_file.read_text())
    config["output_prefix"] = "../../../etc/passwd"
    config_file.write_text(_json.dumps(config))

    payload = [
        {
            "index": 0,
            "text": "t",
            "align_center": False,
            "center_x": False,
            "bw": False,
            "fade_in": False,
            "fade_out": False,
            "text_position": [0, 0],
        }
    ]
    with patch("web.main.subprocess.run", return_value=_make_proc(0)) as mock_run:
        resp = await client.post("/api/generate", json=payload)

    assert resp.status_code == 200
    filename = resp.json()["filename"]
    assert ".." not in filename
    assert "/" not in filename
    # The prefix should only contain safe chars
    prefix = filename.split("_20")[0]
    assert all(c.isalnum() or c in "-_" for c in prefix)

    # The subprocess must have received the sanitized filename
    called_args = mock_run.call_args[0][0]  # positional args list
    assert ".." not in called_args[-1]
    assert "/" not in called_args[-1]
