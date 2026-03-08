"""Google OAuth2 routes: /auth/google, /auth/google/callback, /auth/logout."""
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import SESSION_COOKIE, make_session_cookie, oauth
from db.engine import get_db
from db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
ADMIN_EMAIL  = os.environ.get("ADMIN_EMAIL", "")


@router.get("/google")
async def login_google(request: Request):
    """Redirect the browser to Google's OAuth2 consent page."""
    return await oauth.google.authorize_redirect(request, REDIRECT_URI)


@router.get("/google/callback")
async def auth_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Exchange the OAuth2 code, upsert the user, and set a session cookie."""
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or await oauth.google.userinfo(token=token)

    google_sub = userinfo["sub"]
    email       = userinfo.get("email", "")
    display_name = userinfo.get("name")
    avatar_url   = userinfo.get("picture")
    gmail_refresh_token = token.get("refresh_token")

    # Upsert user
    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            google_sub=google_sub,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            gmail_refresh_token=gmail_refresh_token,
            is_admin=(email == ADMIN_EMAIL and bool(ADMIN_EMAIL)),
        )
        db.add(user)
    else:
        user.email        = email
        user.display_name = display_name
        user.avatar_url   = avatar_url
        if gmail_refresh_token:
            user.gmail_refresh_token = gmail_refresh_token
        # Promote to admin if ADMIN_EMAIL matches and not yet admin
        if ADMIN_EMAIL and email == ADMIN_EMAIL and not user.is_admin:
            user.is_admin = True

    await db.commit()
    await db.refresh(user)

    response = RedirectResponse(url="/")
    response.set_cookie(
        key=SESSION_COOKIE,
        value=make_session_cookie(str(user.id)),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
        secure=os.environ.get("SECURE_COOKIES", "true").lower() != "false",
    )
    return response


@router.post("/logout")
async def logout():
    """Clear the session cookie."""
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response
