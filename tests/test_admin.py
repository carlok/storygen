"""Tests for /api/admin/* endpoints (multi-user only).

Auth-enforcement tests (no DB needed)  ── use multi_client (regular user).
Business-logic tests (mock DB)         ── use admin_client (admin user).
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from tests.conftest import multi_user_only


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user_row(
    user_id=None,
    email="u@test.com",
    is_admin=False,
    is_active=True,
):
    """Return a fake User ORM-like object for mock DB results."""
    from web.db.models import User

    u = User.__new__(User)
    attrs = dict(
        id=user_id or uuid.uuid4(),
        google_sub="sub-" + email,
        email=email,
        display_name=email.split("@")[0],
        avatar_url=None,
        gmail_refresh_token=None,
        is_admin=is_admin,
        is_active=is_active,
        created_at=datetime.now(timezone.utc),
        jobs=[],
        config=None,
    )
    for k, v in attrs.items():
        object.__setattr__(u, k, v)
    return u


# ── Auth enforcement ──────────────────────────────────────────────────────────

@multi_user_only
@pytest.mark.asyncio
async def test_list_users_requires_admin(multi_client):
    """Regular user must receive 403."""
    resp = await multi_client.get("/api/admin/users")
    assert resp.status_code == 403


@multi_user_only
@pytest.mark.asyncio
async def test_get_user_requires_admin(multi_client):
    resp = await multi_client.get(f"/api/admin/users/{uuid.uuid4()}")
    assert resp.status_code == 403


@multi_user_only
@pytest.mark.asyncio
async def test_patch_user_requires_admin(multi_client):
    resp = await multi_client.patch(
        f"/api/admin/users/{uuid.uuid4()}", json={"is_active": False}
    )
    assert resp.status_code == 403


@multi_user_only
@pytest.mark.asyncio
async def test_delete_user_requires_admin(multi_client):
    resp = await multi_client.delete(f"/api/admin/users/{uuid.uuid4()}")
    assert resp.status_code == 403


@multi_user_only
@pytest.mark.asyncio
async def test_stats_requires_admin(multi_client):
    resp = await multi_client.get("/api/admin/stats")
    assert resp.status_code == 403


# ── Admin stats ───────────────────────────────────────────────────────────────

@multi_user_only
@pytest.mark.asyncio
async def test_admin_stats_returns_zeros(admin_client, mock_db_session):
    """With a mock DB returning 0 for all scalar queries → stats all zeros."""
    resp = await admin_client.get("/api/admin/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_users"] == 0
    assert data["total_jobs"] == 0
    assert data["disk_bytes"] == 0


# ── List users ────────────────────────────────────────────────────────────────

@multi_user_only
@pytest.mark.asyncio
async def test_list_users_returns_empty_list(admin_client, mock_db_session):
    """Empty DB → empty list, 200 OK."""
    _, session = mock_db_session
    # Mock returns result.all() == []
    resp = await admin_client.get("/api/admin/users")
    assert resp.status_code == 200
    assert resp.json() == []


@multi_user_only
@pytest.mark.asyncio
async def test_list_users_with_results(admin_client, mock_db_session):
    """Two users in mock DB → list of two UserSummary dicts."""
    _, session = mock_db_session
    u1 = _make_user_row(email="alice@test.com")
    u2 = _make_user_row(email="bob@test.com", is_admin=True)

    mock_result = MagicMock()
    mock_result.all.return_value = [(u1, 3), (u2, 7)]
    session.execute.return_value = mock_result

    resp = await admin_client.get("/api/admin/users")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    emails = {d["email"] for d in data}
    assert emails == {"alice@test.com", "bob@test.com"}
    assert data[1]["is_admin"] is True


# ── Get user ──────────────────────────────────────────────────────────────────

@multi_user_only
@pytest.mark.asyncio
async def test_get_user_not_found(admin_client, mock_db_session):
    """Unknown user ID → 404."""
    _, session = mock_db_session
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    resp = await admin_client.get(f"/api/admin/users/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── Patch user ────────────────────────────────────────────────────────────────

@multi_user_only
@pytest.mark.asyncio
async def test_patch_user_not_found(admin_client, mock_db_session):
    _, session = mock_db_session
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    resp = await admin_client.patch(
        f"/api/admin/users/{uuid.uuid4()}", json={"is_active": False}
    )
    assert resp.status_code == 404


@multi_user_only
@pytest.mark.asyncio
async def test_patch_user_self_demotion_rejected(admin_client, fake_admin, mock_db_session):
    """Admin cannot revoke their own admin rights."""
    _, session = mock_db_session
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_admin
    session.execute.return_value = mock_result

    resp = await admin_client.patch(
        f"/api/admin/users/{fake_admin.id}", json={"is_admin": False}
    )
    assert resp.status_code == 400
    assert "Cannot revoke" in resp.json()["detail"]


# ── Delete user ───────────────────────────────────────────────────────────────

@multi_user_only
@pytest.mark.asyncio
async def test_delete_user_not_found(admin_client, mock_db_session):
    _, session = mock_db_session
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    resp = await admin_client.delete(f"/api/admin/users/{uuid.uuid4()}")
    assert resp.status_code == 404


@multi_user_only
@pytest.mark.asyncio
async def test_delete_user_self_rejected(admin_client, fake_admin, mock_db_session):
    """Admin cannot delete themselves."""
    _, session = mock_db_session
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_admin
    session.execute.return_value = mock_result

    resp = await admin_client.delete(f"/api/admin/users/{fake_admin.id}")
    assert resp.status_code == 400
    assert "Cannot delete yourself" in resp.json()["detail"]
