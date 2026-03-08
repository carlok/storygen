"""Tests for GET /api/blocks."""
import pytest


@pytest.mark.asyncio
async def test_get_blocks_returns_list(client):
    resp = await client.get("/api/blocks")
    assert resp.status_code == 200
    data = resp.json()
    assert "blocks" in data
    assert len(data["blocks"]) == 2


@pytest.mark.asyncio
async def test_get_blocks_first_block_fields(client):
    resp = await client.get("/api/blocks")
    b = resp.json()["blocks"][0]
    assert b["image"] == "photo1.jpg"
    assert b["start"] == 0
    assert b["end"] == 5
    assert b["text"] == "Scene 1"
    assert b["fade_in"] is True
    assert b["fade_out"] is False
    assert b["bw"] is False
    assert b["text_position"] == [100, 900]
    assert b["index"] == 0


@pytest.mark.asyncio
async def test_get_blocks_video_dimensions(client):
    resp = await client.get("/api/blocks")
    data = resp.json()
    assert data["video_width"] == 1080
    assert data["video_height"] == 1920
    assert data["font_size"] == 48


@pytest.mark.asyncio
async def test_get_blocks_defaults_missing_optional_fields(client, config_file):
    """Blocks lacking optional keys get sensible defaults."""
    import json

    # Write a minimal config missing optional per-block fields
    minimal = {
        "output_prefix": "x",
        "fps": 24,
        "width": 1280,
        "height": 720,
        "font_color": [255, 255, 255],
        "music": "m.mp3",
        "blocks": [
            {"image": "a.jpg", "start": 0, "end": 3, "text": "hi"},
        ],
    }
    config_file.write_text(json.dumps(minimal))

    resp = await client.get("/api/blocks")
    assert resp.status_code == 200
    b = resp.json()["blocks"][0]
    assert b["align_center"] is False
    assert b["center_x"] is False
    assert b["bw"] is False
    assert b["fade_in"] is False
    assert b["fade_out"] is False
    assert b["text_position"] == [100, 900]


@pytest.mark.asyncio
async def test_get_blocks_second_block(client):
    resp = await client.get("/api/blocks")
    b = resp.json()["blocks"][1]
    assert b["image"] == "photo2.jpg"
    assert b["bw"] is True
    assert b["align_center"] is True
    assert b["index"] == 1
