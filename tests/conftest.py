"""Shared pytest fixtures for the storygen test suite.

Strategy
--------
- `client`       – async HTTP client; auth / DB dependencies are always overridden
                   so that no real PostgreSQL connection is required.
- `multi_client` – same, but labelled explicitly as a regular non-admin user.
- `admin_client` – same, but authenticated as an admin user.
- Filesystem paths (CONFIG_PATH, OUTPUT_DIR) are always patched to tmp_path.

The app is always multi-user; there is no personal/single-user mode.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ── Set env vars BEFORE importing web.main ───────────────────────────────────
os.environ.setdefault("SECRET_KEY", "test-secret-key-32chars-abcde-xyz0!")

# ── Import app after env setup ────────────────────────────────────────────────
from web.main import app  # noqa: E402

# ── Always import auth/db deps (used to register dependency_overrides) ────────
# Use bare-name imports to match what web/main.py imports, ensuring the same
# function objects are used as keys in app.dependency_overrides.
from auth import get_current_user, require_admin  # type: ignore[import]  # noqa: E402
from db.engine import get_db  # type: ignore[import]  # noqa: E402


# ── Sample config ─────────────────────────────────────────────────────────────

SAMPLE_CONFIG: dict = {
    "output_prefix": "testvid",
    "fps": 24,
    "width": 1080,
    "height": 1920,
    "font_size": 48,
    "font_color": [255, 255, 255],
    "music": "music/track.mp3",
    "blocks": [
        {
            "image": "photo1.jpg",
            "start": 0,
            "end": 5,
            "text": "Scene 1",
            "bw": False,
            "fade_in": True,
            "fade_out": False,
            "text_position": [100, 900],
            "align_center": False,
            "center_x": False,
        },
        {
            "image": "photo2.jpg",
            "start": 5,
            "end": 10,
            "text": "Scene 2",
            "bw": True,
            "fade_in": False,
            "fade_out": True,
            "text_position": [200, 600],
            "align_center": True,
            "center_x": False,
        },
    ],
}


@pytest.fixture
def sample_config() -> dict:
    import copy
    return copy.deepcopy(SAMPLE_CONFIG)


@pytest.fixture
def config_file(tmp_path: Path, sample_config: dict) -> Path:
    f = tmp_path / "config.json"
    f.write_text(json.dumps(sample_config))
    return f


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "output"
    d.mkdir()
    return d


@pytest.fixture
def fake_mp4(output_dir: Path) -> Path:
    """A zero-content .mp4 file for download / email tests."""
    mp4 = output_dir / "testvid_2025-01-01-00-00-00.mp4"
    mp4.write_bytes(b"\x00" * 64)
    return mp4


# ── Mock DB session ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_db_session():
    """
    Returns ``(get_db_override, session)`` where ``get_db_override`` is an
    async generator suitable for ``app.dependency_overrides[get_db]`` and
    ``session`` is the underlying AsyncMock for assertions.
    """
    result = MagicMock()
    result.scalar_one.return_value = 0
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    result.all.return_value = []

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()

    async def _get_db_override():
        yield session

    return _get_db_override, session


# ── Fake ORM user builder ─────────────────────────────────────────────────────

def _make_user(**kwargs):
    """
    Build a fake user object that quacks like ``web.db.models.User``.

    Uses SimpleNamespace instead of the real ORM class so that SQLAlchemy's
    data descriptors never fire (they require a fully-initialized mapper state
    that `User.__new__` alone does not set up).  The dependency overrides in
    each fixture replace the real `get_current_user` / `require_admin` with
    lambdas that return this object, so FastAPI never type-checks it.
    """
    from types import SimpleNamespace

    defaults = dict(
        id=uuid.uuid4(),
        google_sub="sub-regular",
        email="user@test.com",
        display_name="Test User",
        avatar_url=None,
        gmail_refresh_token=None,
        is_admin=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        jobs=[],
        config=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── User fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def fake_user():
    return _make_user()


@pytest.fixture
def fake_admin():
    return _make_user(
        google_sub="sub-admin",
        email="admin@test.com",
        display_name="Admin User",
        is_admin=True,
    )


# ── Core client ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(monkeypatch, config_file, output_dir, mock_db_session):
    """
    Async HTTP client that patches filesystem paths and injects a regular
    fake user so that auth-protected endpoints work without a real DB.
    """
    import web.main as _main

    monkeypatch.setattr(_main, "CONFIG_PATH", config_file)
    monkeypatch.setattr(_main, "OUTPUT_DIR", output_dir)

    fake = _make_user()
    get_db_override, _ = mock_db_session
    app.dependency_overrides[get_current_user] = lambda: fake
    app.dependency_overrides[get_db] = get_db_override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Named user clients ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def multi_client(monkeypatch, config_file, output_dir, fake_user, mock_db_session):
    """Client authenticated as a non-admin user."""
    import web.main as _main

    monkeypatch.setattr(_main, "CONFIG_PATH", config_file)
    monkeypatch.setattr(_main, "OUTPUT_DIR", output_dir)

    get_db_override, _ = mock_db_session
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = get_db_override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_client(monkeypatch, config_file, output_dir, fake_admin, mock_db_session):
    """Client authenticated as an admin user."""
    import web.main as _main

    monkeypatch.setattr(_main, "CONFIG_PATH", config_file)
    monkeypatch.setattr(_main, "OUTPUT_DIR", output_dir)

    get_db_override, _ = mock_db_session
    app.dependency_overrides[get_current_user] = lambda: fake_admin
    app.dependency_overrides[require_admin] = lambda: fake_admin
    app.dependency_overrides[get_db] = get_db_override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
