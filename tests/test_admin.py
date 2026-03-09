"""Tests for /api/admin/* endpoints.

Auth-enforcement tests (no DB needed)  ── use multi_client (regular user).
Business-logic tests (mock DB)         ── use admin_client (admin user).
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user_row(
    user_id=None,
    email="u@test.com",
    is_admin=False,
    is_active=True,
):
    """Return a fake User-like object for mock DB results (SimpleNamespace)."""
    from types import SimpleNamespace

    return SimpleNamespace(
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


# ── Auth enforcement ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_users_requires_admin(multi_client):
    """Regular user must receive 403."""
    resp = await multi_client.get("/api/admin/users")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_user_requires_admin(multi_client):
    resp = await multi_client.get(f"/api/admin/users/{uuid.uuid4()}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_user_requires_admin(multi_client):
    resp = await multi_client.patch(
        f"/api/admin/users/{uuid.uuid4()}", json={"is_active": False}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_user_requires_admin(multi_client):
    resp = await multi_client.delete(f"/api/admin/users/{uuid.uuid4()}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_stats_requires_admin(multi_client):
    resp = await multi_client.get("/api/admin/stats")
    assert resp.status_code == 403


# ── Admin stats ───────────────────────────────────────────────────────────────

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

@pytest.mark.asyncio
async def test_list_users_returns_empty_list(admin_client, mock_db_session):
    """Empty DB → empty list, 200 OK."""
    _, session = mock_db_session
    # Mock returns result.all() == []
    resp = await admin_client.get("/api/admin/users")
    assert resp.status_code == 200
    assert resp.json() == []


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

@pytest.mark.asyncio
async def test_delete_user_not_found(admin_client, mock_db_session):
    _, session = mock_db_session
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    resp = await admin_client.delete(f"/api/admin/users/{uuid.uuid4()}")
    assert resp.status_code == 404


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


# ── Happy-path success tests (cover lines currently at 0%) ───────────────────

@pytest.mark.asyncio
async def test_admin_stats_iterates_users(admin_client, mock_db_session):
    """Stats endpoint calls _user_storage_bytes for each user ID returned by DB."""
    _, session = mock_db_session

    call_idx = [0]

    def make_execute_result():
        """Return a fresh MagicMock for each execute() call."""
        from unittest.mock import MagicMock

        r = MagicMock()
        if call_idx[0] == 0:   # total_users
            r.scalar_one.return_value = 2
        elif call_idx[0] == 1:  # total_jobs
            r.scalar_one.return_value = 5
        else:                   # user IDs for disk — return one fake UUID
            r.scalars.return_value = iter([str(uuid.uuid4())])
        call_idx[0] += 1
        return r

    from unittest.mock import AsyncMock
    session.execute = AsyncMock(side_effect=lambda *a, **kw: make_execute_result())

    resp = await admin_client.get("/api/admin/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_users"] == 2
    assert data["total_jobs"] == 5
    assert data["disk_bytes"] == 0   # storage dir doesn't exist → 0 bytes


@pytest.mark.asyncio
async def test_get_user_found(admin_client, mock_db_session):
    """GET /api/admin/users/{id} returns full detail when user exists."""
    _, session = mock_db_session
    from types import SimpleNamespace

    job = SimpleNamespace(
        id=uuid.uuid4(),
        filename="vid.mp4",
        status="done",
        created_at=datetime.now(timezone.utc),
    )
    user = _make_user_row(email="alice@test.com")
    # Give user a jobs attribute (SimpleNamespace supports attribute assignment)
    user.jobs = [job]

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    session.execute.return_value = mock_result

    resp = await admin_client.get(f"/api/admin/users/{user.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "alice@test.com"
    assert data["job_count"] == 1
    assert len(data["recent_jobs"]) == 1
    assert data["recent_jobs"][0]["filename"] == "vid.mp4"


@pytest.mark.asyncio
async def test_patch_user_success(admin_client, fake_admin, mock_db_session):
    """PATCH /api/admin/users/{id} applies changes and returns updated UserSummary."""
    _, session = mock_db_session

    target = _make_user_row(email="target@test.com")

    call_idx = [0]

    def make_execute_result():
        from unittest.mock import MagicMock
        r = MagicMock()
        if call_idx[0] == 0:   # fetch user
            r.scalar_one_or_none.return_value = target
        else:                   # job count after commit
            r.scalar_one.return_value = 0
        call_idx[0] += 1
        return r

    from unittest.mock import AsyncMock
    session.execute = AsyncMock(side_effect=lambda *a, **kw: make_execute_result())
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    resp = await admin_client.patch(
        f"/api/admin/users/{target.id}", json={"is_active": False}
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_user_success(admin_client, fake_admin, mock_db_session):
    """DELETE /api/admin/users/{id} returns 204 and calls session.delete."""
    _, session = mock_db_session

    target = _make_user_row(email="gone@test.com")

    from unittest.mock import AsyncMock

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = target
    session.execute.return_value = mock_result
    session.delete = AsyncMock()
    session.commit = AsyncMock()

    resp = await admin_client.delete(f"/api/admin/users/{target.id}")
    assert resp.status_code == 204
    session.delete.assert_called_once_with(target)
    session.commit.assert_called()
