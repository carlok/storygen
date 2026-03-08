"""Tests for GET /api/me (multi-user only)."""
import pytest

from tests.conftest import multi_user_only


@multi_user_only
@pytest.mark.asyncio
async def test_me_returns_user_info(multi_client, fake_user):
    resp = await multi_client.get("/api/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == fake_user.email
    assert data["display_name"] == fake_user.display_name
    assert data["is_admin"] is False
    assert data["is_active"] is True
    assert "id" in data


@multi_user_only
@pytest.mark.asyncio
async def test_me_admin_flag_for_admin_user(admin_client, fake_admin):
    resp = await admin_client.get("/api/me")
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is True


@multi_user_only
@pytest.mark.asyncio
async def test_me_unauthenticated_returns_401(monkeypatch, config_file, output_dir):
    """Without an auth override, calling /api/me with no session cookie → 401."""
    from httpx import ASGITransport, AsyncClient
    from web.main import app

    import web.main as _main
    monkeypatch.setattr(_main, "CONFIG_PATH", config_file)
    monkeypatch.setattr(_main, "OUTPUT_DIR", output_dir)

    # No dependency_overrides → real get_current_user runs → no cookie → 401
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/me")
    assert resp.status_code == 401
