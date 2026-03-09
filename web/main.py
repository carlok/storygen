import json
import logging
import os
import re
import smtplib
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Annotated, List

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
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
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
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

    Raises HTTPException(500) when SMTP is not configured so callers in request
    context get a clean error.  Call sites in background tasks should wrap it
    themselves (see _notify_admin).
    """
    host      = os.environ.get("SMTP_HOST", "")
    port      = int(os.environ.get("SMTP_PORT", "587"))
    user      = os.environ.get("SMTP_USER", "")
    password  = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("SMTP_FROM", "")
    if not host or not from_addr:
        raise HTTPException(500, "SMTP not configured — set SMTP_HOST and SMTP_FROM env vars")

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

    # ── Write per-user temp config and run subprocess ─────────────────────────
    # Use tempfile.mkstemp for a file with restricted permissions (0o600 by default)
    # instead of a predictable path under the world-readable /tmp directory.
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="storygen_", suffix=".json")
    tmp_config = Path(tmp_path)
    try:
        with os.fdopen(tmp_fd, "w") as tmp_file:
            json.dump(cfg, tmp_file)
        result = subprocess.run(
            [sys.executable, str(GENERATE_SCRIPT), filename, tmp_path],
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute hard cap — prevents runaway processes
        )
    except subprocess.TimeoutExpired:
        _log.error("generate.py timed out for user %s", _auth.id)
        db.add(Job(user_id=_auth.id, filename=filename, status="failed", error="timeout"))
        await db.commit()
        raise HTTPException(504, "Video generation timed out")
    finally:
        tmp_config.unlink(missing_ok=True)

    # ── Record Job (success or failure counts toward daily limit) ──────────────
    status    = "done" if result.returncode == 0 else "failed"
    error_msg = result.stderr[:512] if result.returncode != 0 else None
    db.add(Job(user_id=_auth.id, filename=filename, status=status, error=error_msg))
    await db.commit()

    if result.returncode != 0:
        _log.error("generate.py failed for user %s: %s", _auth.id, result.stderr)
        raise HTTPException(500, "Video generation failed")

    # ── Admin notification ─────────────────────────────────────────────────────
    background_tasks.add_task(
        _notify_admin,
        f"[storygen] New video by {_auth.email}: {filename}",
        f"User {_auth.email} (id={_auth.id}) generated video '{filename}'.",
    )

    return {"status": "ok", "filename": filename}


@app.get("/api/image/{filename}")
def get_image(filename: str, _auth: User = Depends(_auth_dep)):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    image_path = Path("/assets/images") / filename
    if not image_path.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(path=str(image_path))


@app.get("/api/video")
def get_video(
    name: str = Query(..., description="Filename returned by /api/generate"),
    _auth: User = Depends(_auth_dep),
):
    try:
        video_path = (OUTPUT_DIR / name).resolve()
    except Exception:
        raise HTTPException(400, "Invalid filename")
    output_root = str(OUTPUT_DIR.resolve()) + os.sep
    if not str(video_path).startswith(output_root):
        raise HTTPException(400, "Invalid filename")
    if not video_path.exists() or video_path.suffix != ".mp4":
        raise HTTPException(404, "Video not found")
    return FileResponse(path=str(video_path), media_type="video/mp4", filename=name)


class EmailRequest(BaseModel):
    to: str
    filename: str


@app.post("/api/send-email")
def send_email(req: EmailRequest, _auth: User = Depends(_auth_dep)):
    if _auth.email != req.to:
        raise HTTPException(403, "You can only send to your own email address")

    try:
        video_path = (OUTPUT_DIR / req.filename).resolve()
    except Exception:
        raise HTTPException(400, "Invalid filename")
    output_root = str(OUTPUT_DIR.resolve()) + os.sep
    if not str(video_path).startswith(output_root):
        raise HTTPException(400, "Invalid filename")
    if not video_path.exists() or video_path.suffix != ".mp4":
        raise HTTPException(404, "Video not found")

    try:
        _smtp_send(
            req.to,
            f"Generated video: {req.filename}",
            "Your story video is attached.",
            attachment=video_path,
        )
    except HTTPException:
        raise
    except Exception as exc:
        _log.error("send_email failed for user %s: %s", _auth.id, exc)
        raise HTTPException(500, "Email delivery failed") from exc
    return {"status": "ok"}


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
        from sqlalchemy import update
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(User).where(User.email == admin_email).values(is_admin=True)
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
    return {"detail": "Frontend not built yet"}
