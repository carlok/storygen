"""Google OAuth2 + session-cookie auth helpers."""
import os
from typing import Annotated

from authlib.integrations.starlette_client import OAuth
from fastapi import Cookie, Depends, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db.engine import get_db
from .db.models import User

# ── OAuth client ────────────────────────────────────────────────────────────

oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
        # Uncomment to also request Gmail send scope:
        # "scope": "openid email profile https://www.googleapis.com/auth/gmail.send",
    },
)

# ── Session cookie (signed, not encrypted) ──────────────────────────────────

_raw_key = os.environ.get("SECRET_KEY", "")
if not _raw_key or _raw_key == "change-me":
    raise RuntimeError(
        "SECRET_KEY env var is not set or still 'change-me'.\n"
        "Generate a strong key: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
SECRET_KEY = _raw_key
SESSION_COOKIE = "storygen_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

_signer = URLSafeTimedSerializer(SECRET_KEY, salt="session")


def make_session_cookie(user_id: str) -> str:
    return _signer.dumps(user_id)


def read_session_cookie(token: str) -> str | None:
    try:
        return _signer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


# ── FastAPI dependencies ─────────────────────────────────────────────────────

async def get_current_user(
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return the authenticated User or raise 401."""
    if not session:
        raise HTTPException(401, "Not authenticated")

    user_id = read_session_cookie(session)
    if not user_id:
        raise HTTPException(401, "Session expired")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Raise 403 if the current user is not an admin."""
    if not user.is_admin:
        raise HTTPException(403, "Forbidden")
    return user
