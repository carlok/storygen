"""Tests for GET /api/video — path traversal security and happy path."""
import pytest


@pytest.mark.asyncio
async def test_get_video_not_found(client):
    resp = await client.get("/api/video", params={"name": "missing.mp4"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_video_success(client, fake_mp4):
    resp = await client.get("/api/video", params={"name": fake_mp4.name})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "video/mp4"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    [
        "../config.json",
        "../../etc/passwd",
        "%2e%2e%2fconfig.json",
        "subdir/../../../etc/passwd",
        "/etc/passwd",
    ],
)
async def test_get_video_path_traversal_rejected(client, name):
    """Path traversal attempts must be rejected with 400 or 404."""
    resp = await client.get("/api/video", params={"name": name})
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_get_video_non_mp4_rejected(client, output_dir):
    """Non-.mp4 extensions must be rejected."""
    (output_dir / "config.json").write_text("{}")
    resp = await client.get("/api/video", params={"name": "config.json"})
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_get_video_directory_traversal_with_null_byte(client):
    """Null-byte injection attempts should not cause server errors."""
    resp = await client.get("/api/video", params={"name": "foo\x00.mp4"})
    assert resp.status_code in (400, 404, 422)
