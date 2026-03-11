import asyncio
import json
import logging
import os
import re
import smtplib
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import date, datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Annotated, List

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from auth import get_current_user, require_admin
from db.engine import AsyncSessionLocal, get_db
from db.models import Config, Job, User
from routers.admin import router as admin_router
from routers.auth import router as auth_router

# ── Path constants ─────────────────────────────────────────────────────────────
CONFIG_PATH     = Path("/assets/config.json")
OUTPUT_DIR      = Path("/output")
GENERATE_SCRIPT = Path("/src/generate.py")

_STATIC_DIR = Path(__file__).parent / "static"
_ASSETS_DIR = _STATIC_DIR / "assets"
_SPA_INDEX  = _STATIC_DIR / "index.html"

_log = logging.getLogger(__name__)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI()

# ── Secret key (always required) ───────────────────────────────────────────────
_SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not _SECRET_KEY or _SECRET_KEY == "change-me":
    raise RuntimeError(
        "SECRET_KEY env var must be set to a strong random secret.\n"
        "Generate one: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

# ── Security headers middleware ─────────────────────────────────────────────────
# Matches literal ".." and any percent-encoding of ".." (%2e%2e, %2E%2E, etc.)
_TRAVERSAL_RAW_RE = re.compile(rb"(\.\.|%2e%2e)", re.IGNORECASE)
# Matches decoded paths whose segments include ".." or resolved system directory roots
# that are never valid web-app routes (guards against client-normalized traversal).
_TRAVERSAL_SEG_RE = re.compile(r"(^|/)\.\.(/|$)")
_UNIX_SYSROOT_RE = re.compile(
    r"^/(etc|usr|var|proc|sys|home|root|bin|sbin|lib|tmp|dev|mnt|media|run|srv|boot|opt)(/|$)"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Reject requests whose raw path contains traversal sequences (literal or
        # percent-encoded), or whose decoded path resolves into Unix system roots
        # that can only arrive via client-normalized traversal.
        raw_path: bytes = request.scope.get("raw_path", b"") or b""
        decoded_path: str = request.scope.get("path", "") or ""
        if _TRAVERSAL_RAW_RE.search(raw_path):
            _log.warning(
                "path traversal blocked: raw=%s client=%s",
                request.url.path,
                getattr(request.client, "host", "unknown"),
            )
            return JSONResponse({"detail": "Invalid path"}, status_code=400)
        if _TRAVERSAL_SEG_RE.search(decoded_path):
            _log.warning(
                "path traversal blocked: raw=%s client=%s",
                request.url.path,
                getattr(request.client, "host", "unknown"),
            )
            return JSONResponse({"detail": "Invalid path"}, status_code=400)
        if _UNIX_SYSROOT_RE.match(decoded_path):
            _log.warning(
                "path traversal blocked: raw=%s client=%s",
                request.url.path,
                getattr(request.client, "host", "unknown"),
            )
            return JSONResponse({"detail": "Invalid path"}, status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # HSTS only over HTTPS (i.e. when SECURE_COOKIES is not disabled)
        if os.environ.get("SECURE_COOKIES", "true").lower() != "false":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://lh3.googleusercontent.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        return response


# SessionMiddleware is required for OAuth state CSRF protection.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SessionMiddleware, secret_key=_SECRET_KEY)

app.include_router(auth_router)
app.include_router(admin_router)


# ── Auth dependency ────────────────────────────────────────────────────────────

async def _auth_dep(user: User = Depends(get_current_user)) -> User:
    return user


# ── SMTP helpers ───────────────────────────────────────────────────────────────

def _smtp_send(
    to: str,
    subject: str,
    body: str,
    attachment: Path | None = None,
) -> None:
    """Send an email via stdlib smtplib (STARTTLS on port 587).

    Raises RuntimeError when SMTP is not configured.  Callers in a request
    context should convert this to HTTPException; background callers log it.
    """
    host      = os.environ.get("SMTP_HOST", "")
    port      = int(os.environ.get("SMTP_PORT", "587"))
    user      = os.environ.get("SMTP_USER", "")
    password  = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("SMTP_FROM", "")
    if not host or not from_addr:
        raise RuntimeError("SMTP not configured — set SMTP_HOST and SMTP_FROM env vars")

    msg = MIMEMultipart()
    msg["From"]    = from_addr
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if attachment:
        part = MIMEBase("video", "mp4")
        part.set_payload(attachment.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=attachment.name)
        msg.attach(part)

    with smtplib.SMTP(host, port) as srv:
        srv.starttls()
        if user and password:
            srv.login(user, password)
        srv.send_message(msg)


def _smtp_configured() -> bool:
    """Return True if the minimum SMTP vars are present."""
    return bool(os.environ.get("SMTP_HOST")) and bool(os.environ.get("SMTP_FROM"))


def _notify_admin(subject: str, body: str) -> None:
    """Fire-and-forget admin notification.

    Sync function — FastAPI dispatches it to a thread pool via BackgroundTasks,
    so blocking SMTP I/O never stalls the async event loop.
    """
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if not admin_email:
        return
    try:
        _smtp_send(admin_email, subject, body)
    except Exception:
        _log.warning("admin notify failed: %s", subject)


# ── Per-user config helpers ────────────────────────────────────────────────────

def _read_template() -> dict:
    """Read the shared template config from /assets/config.json."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


async def _get_user_config(db: AsyncSession, user_id) -> Config:
    """Return the user's Config row, seeding from the template on first access."""
    result = await db.execute(select(Config).where(Config.user_id == user_id))
    cfg_row = result.scalar_one_or_none()
    if cfg_row is None:
        data = _read_template()
        cfg_row = Config(user_id=user_id, data=data)
        db.add(cfg_row)
        await db.commit()
        await db.refresh(cfg_row)
    return cfg_row


# ── Background video generation task ──────────────────────────────────────────

async def _run_generate_and_email(
    user_id: str,
    user_email: str,
    filename: str,
    tmp_path: str,
    job_id: str,
) -> None:
    """Background task: run generate.py, update the Job row, then email the result.

    Uses asyncio.to_thread so the blocking subprocess never stalls the event loop.
    Opens its own DB session (cannot reuse the request-scoped session).
    """
    status    = "failed"
    error_msg = "unknown"
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, str(GENERATE_SCRIPT), filename, tmp_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            status    = "done"
            error_msg = None
        else:
            error_msg = result.stderr[:512]
            _log.error("generate.py failed for user %s: %s", user_id, result.stderr)
    except subprocess.TimeoutExpired:
        error_msg = "timeout"
        _log.error("generate.py timed out for user %s", user_id)
    except Exception as exc:
        error_msg = str(exc)[:512]
        _log.error("unexpected error in _run_generate_and_email for user %s: %s", user_id, exc)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # ── Update job row ──────────────────────────────────────────────────────────
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                sa_update(Job)
                .where(Job.id == job_id)
                .values(status=status, error=error_msg)
            )
            await db.commit()
    except Exception as exc:
        _log.error("failed to update job %s: %s", job_id, exc)

    # ── Send email on success ───────────────────────────────────────────────────
    if status == "done":
        try:
            _smtp_send(
                user_email,
                "Your story video is ready",
                "Your video has been generated and is attached to this email.",
                attachment=OUTPUT_DIR / filename,
            )
        except Exception as exc:
            _log.error("email failed for user %s after generation: %s", user_id, exc)

        # Admin notification (fire-and-forget)
        _notify_admin(
            f"[storygen] New video by {user_email}: {filename}",
            f"User {user_email} (id={user_id}) generated video '{filename}'.",
        )


# ── Core API routes ────────────────────────────────────────────────────────────

@app.get("/api/blocks")
async def get_blocks(
    _auth: User = Depends(_auth_dep),
    db: AsyncSession = Depends(get_db),
):
    cfg_row = await _get_user_config(db, _auth.id)
    cfg = cfg_row.data
    blocks = [
        {
            "index": i,
            "image": b["image"],
            "start": b["start"],
            "end": b["end"],
            "text": b.get("text", ""),
            "align_center": b.get("align_center", False),
            "center_x": b.get("center_x", False),
            "bw": b.get("bw", False),
            "fade_in": b.get("fade_in", False),
            "fade_out": b.get("fade_out", False),
            "text_position": b.get("text_position", [100, 900]),
        }
        for i, b in enumerate(cfg["blocks"])
    ]
    return {
        "blocks": blocks,
        "video_width": cfg["width"],
        "video_height": cfg["height"],
        "font_size": cfg.get("font_size", 48),
    }


class BlockUpdate(BaseModel):
    index: int = Field(..., ge=0)
    text: str = Field(..., max_length=2000)
    align_center: bool = False
    center_x: bool = False
    bw: bool = False
    fade_in: bool = False
    fade_out: bool = False
    text_position: list[int] = Field(default=[100, 900])

    @field_validator("text_position")
    @classmethod
    def validate_text_position(cls, v: list[int]) -> list[int]:
        if len(v) != 2:
            raise ValueError("text_position must be a list of exactly 2 integers [x, y]")
        return v


@app.post("/api/generate")
async def generate(
    updates: List[BlockUpdate],
    background_tasks: BackgroundTasks,
    _auth: User = Depends(_auth_dep),
    db: AsyncSession = Depends(get_db),
):
    # ── SMTP pre-flight check — fail fast before queuing ──────────────────────
    if not _smtp_configured():
        raise HTTPException(500, "Email delivery not configured — contact the administrator")

    # ── Daily limit check ──────────────────────────────────────────────────────
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    today_count = (
        await db.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.user_id == _auth.id)
            .where(Job.created_at >= today_start)
        )
    ).scalar_one()
    limit = int(os.environ.get("DAILY_VIDEO_LIMIT", "3"))
    if today_count >= limit:
        raise HTTPException(
            429, f"Daily limit of {limit} videos reached. Try again tomorrow."
        )

    # ── Load & update per-user config ──────────────────────────────────────────
    cfg_row = await _get_user_config(db, _auth.id)
    # Work on a deep copy so we can safely reassign cfg_row.data
    cfg = json.loads(json.dumps(cfg_row.data))

    for u in updates:
        if u.index < 0 or u.index >= len(cfg["blocks"]):
            raise HTTPException(400, f"Invalid block index: {u.index}")
        cfg["blocks"][u.index] = {
            **cfg["blocks"][u.index],
            "text": u.text,
            "align_center": u.align_center,
            "center_x": u.center_x,
            "bw": u.bw,
            "fade_in": u.fade_in,
            "fade_out": u.fade_out,
            "text_position": u.text_position,
        }

    # Persist updated config (replacing the whole JSONB triggers change detection)
    cfg_row.data = cfg
    await db.commit()

    # ── Build output filename ──────────────────────────────────────────────────
    raw_prefix = str(cfg.get("output_prefix", "video") or "video")
    prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_prefix)[:32]
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    filename = f"{prefix}_{timestamp}.mp4"

    # ── Write temp config — background task owns cleanup ─────────────────────
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="storygen_", suffix=".json")
    with os.fdopen(tmp_fd, "w") as tmp_file:
        json.dump(cfg, tmp_file)

    # ── Insert pending Job (counts toward daily limit immediately) ────────────
    job = Job(user_id=_auth.id, filename=filename, status="pending")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # ── Queue background task and return immediately ───────────────────────────
    background_tasks.add_task(
        _run_generate_and_email,
        str(_auth.id),
        _auth.email,
        filename,
        tmp_path,
        str(job.id),
    )

    return {"status": "queued"}


@app.get("/api/image/{filename}")
def get_image(filename: str, _auth: User = Depends(_auth_dep)):
    _images_root = Path("/assets/images").resolve()
    # URL-decode first so that %2F-encoded slashes are also caught by resolve()
    decoded = urllib.parse.unquote(filename)
    try:
        safe = (_images_root / decoded).resolve()
    except Exception:
        raise HTTPException(400, "Invalid filename")
    if not safe.is_relative_to(_images_root):
        raise HTTPException(400, "Invalid filename")
    if not safe.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(path=str(safe))


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
async def health():
    """Liveness probe for Railway, Kubernetes, and load balancers."""
    return {"status": "ok"}


# ── Auth, Me & Admin page ─────────────────────────────────────────────────────

@app.get("/api/me")
async def me(user: Annotated[User, Depends(get_current_user)]):
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
    }


@app.get("/admin")
async def admin_page(_admin: User = Depends(require_admin)):
    if _SPA_INDEX.exists():
        return FileResponse(str(_SPA_INDEX))
    return {"detail": "Frontend not built yet"}


@app.on_event("startup")
async def promote_initial_admin():
    """Promote ADMIN_EMAIL to admin on first startup (no manual SQL needed)."""
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if not admin_email:
        return
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                sa_update(User).where(User.email == admin_email).values(is_admin=True)
            )
            await db.commit()
    except Exception as exc:
        _log.warning("promote_initial_admin skipped (run migrations first): %s", exc)


# ── Static files ──────────────────────────────────────────────────────────────
# Vite's hashed JS/CSS bundles live under /assets.
# Guard: skip mount if the directory does not exist (frontend not yet built).
if _ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="assets")


# SPA catch-all: any path not already matched by an API route above gets
# index.html so React Router handles client-side navigation.
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):  # noqa: ARG001
    if _SPA_INDEX.exists():
        return FileResponse(str(_SPA_INDEX))
    raise HTTPException(404, "Not found")
