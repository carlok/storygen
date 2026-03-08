import base64
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Annotated, List

import resend

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

CONFIG_PATH = Path("/assets/config.json")
OUTPUT_DIR  = Path("/output")
GENERATE_SCRIPT = Path("/src/generate.py")

app = FastAPI()

# ── Mode detection ────────────────────────────────────────────────────────────
_multi_user = bool(os.environ.get("DATABASE_URL"))

# ── Secret key: required in multi-user mode, placeholder otherwise ────────────
# Fix #1 / CRITICAL: insecure default "change-me" is rejected at startup.
_SECRET_KEY = os.environ.get("SECRET_KEY", "")
if _multi_user and (not _SECRET_KEY or _SECRET_KEY == "change-me"):
    raise RuntimeError(
        "SECRET_KEY env var must be set to a strong random secret in multi-user mode.\n"
        "Generate one: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

# SessionMiddleware is required for OAuth state CSRF protection.
app.add_middleware(
    SessionMiddleware,
    secret_key=_SECRET_KEY or "personal-mode-placeholder-not-used-for-auth",
)

# ── Routers (only loaded when DATABASE_URL is set) ────────────────────────────
if _multi_user:
    from routers.auth import router as auth_router
    from routers.admin import router as admin_router
    from auth import get_current_user, require_admin
    from db.models import User
    app.include_router(auth_router)
    app.include_router(admin_router)

# ── Conditional auth dependency ───────────────────────────────────────────────
# Fix #3 / CRITICAL: in multi-user mode, all core /api/* routes require a
# valid session. In personal mode the dependency is a no-op (returns None).
if _multi_user:
    async def _auth_dep(user=Depends(get_current_user)):
        return user
else:
    async def _auth_dep():  # type: ignore[misc]
        return None


# ── Config helpers ────────────────────────────────────────────────────────────

def read_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def write_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ── Core API routes ───────────────────────────────────────────────────────────

@app.get("/api/blocks")
def get_blocks(_auth=Depends(_auth_dep)):
    cfg = read_config()
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
    index: int
    text: str
    align_center: bool = False
    center_x: bool = False
    bw: bool = False
    fade_in: bool = False
    fade_out: bool = False
    text_position: list[int] = [100, 900]


@app.post("/api/generate")
def generate(updates: List[BlockUpdate], _auth=Depends(_auth_dep)):
    cfg = read_config()

    for u in updates:
        if u.index < 0 or u.index >= len(cfg["blocks"]):
            raise HTTPException(status_code=400, detail=f"Invalid block index: {u.index}")
        cfg["blocks"][u.index]["text"] = u.text
        cfg["blocks"][u.index]["align_center"] = u.align_center
        cfg["blocks"][u.index]["center_x"] = u.center_x
        cfg["blocks"][u.index]["bw"] = u.bw
        cfg["blocks"][u.index]["fade_in"] = u.fade_in
        cfg["blocks"][u.index]["fade_out"] = u.fade_out
        cfg["blocks"][u.index]["text_position"] = u.text_position

    write_config(cfg)

    # Fix #9 / MEDIUM: sanitize output_prefix — allow only [a-zA-Z0-9_-]
    # so it can never inject path separators into the subprocess argument.
    raw_prefix = str(cfg.get("output_prefix", "video") or "video")
    prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_prefix)[:32]
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    filename = f"{prefix}_{timestamp}.mp4"

    result = subprocess.run(
        ["python", str(GENERATE_SCRIPT), filename],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=result.stderr or "Video generation failed",
        )

    return {"status": "ok", "filename": filename}


@app.get("/api/image/{filename}")
def get_image(filename: str, _auth=Depends(_auth_dep)):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    image_path = Path("/assets/images") / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path=str(image_path))


@app.get("/api/video")
def get_video(
    name: str = Query(..., description="Filename returned by /api/generate"),
    _auth=Depends(_auth_dep),
):
    # Fix #2 / CRITICAL + Fix #4 / HIGH: resolve path and assert it stays
    # inside OUTPUT_DIR; also fixes the operator-precedence ambiguity.
    try:
        video_path = (OUTPUT_DIR / name).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid filename")
    output_root = str(OUTPUT_DIR.resolve()) + os.sep
    if not str(video_path).startswith(output_root):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not video_path.exists() or video_path.suffix != ".mp4":
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(path=str(video_path), media_type="video/mp4", filename=name)


class EmailRequest(BaseModel):
    to: str
    filename: str


@app.post("/api/send-email")
def send_email(req: EmailRequest, _auth=Depends(_auth_dep)):
    # Fix #8 / HIGH: in multi-user mode, only allow sending to the authenticated
    # user's own email — prevents using this as an open relay.
    if _multi_user and _auth is not None and req.to != _auth.email:
        raise HTTPException(
            status_code=403,
            detail="You can only send to your own email address",
        )

    # Path traversal guard on the filename (same pattern as /api/video)
    try:
        video_path = (OUTPUT_DIR / req.filename).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid filename")
    output_root = str(OUTPUT_DIR.resolve()) + os.sep
    if not str(video_path).startswith(output_root):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not video_path.exists() or video_path.suffix != ".mp4":
        raise HTTPException(status_code=404, detail="Video not found")

    api_key  = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("RESEND_FROM", "")
    if not api_key or not from_addr:
        raise HTTPException(
            status_code=500,
            detail="Resend not configured — set RESEND_API_KEY and RESEND_FROM env vars",
        )

    resend.api_key = api_key

    with open(video_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    try:
        resend.Emails.send({
            "from": from_addr,
            "to": [req.to],
            "subject": f"Generated video: {req.filename}",
            "text": "Your story video is attached.",
            "attachments": [{"filename": req.filename, "content": content}],
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok"}


# ── Multi-user endpoints ──────────────────────────────────────────────────────

if _multi_user:
    @app.get("/api/me")
    async def me(user: Annotated["User", Depends(get_current_user)]):
        return {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
        }

    # Fix #10 / MEDIUM: gate the admin HTML page behind require_admin so the
    # UI structure is not disclosed to unauthenticated or non-admin users.
    @app.get("/admin")
    async def admin_page(_admin=Depends(require_admin)):
        return FileResponse("static/admin.html")

    @app.on_event("startup")
    async def promote_initial_admin():
        """Promote ADMIN_EMAIL to admin on first startup (no manual SQL needed).
        Wrapped in try/except so a missing table or DB hiccup doesn't crash startup.
        """
        admin_email = os.environ.get("ADMIN_EMAIL", "")
        if not admin_email:
            return
        try:
            from sqlalchemy import update
            from db.engine import AsyncSessionLocal
            from db.models import User as UserModel
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(UserModel)
                    .where(UserModel.email == admin_email)
                    .values(is_admin=True)
                )
                await db.commit()
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning(
                "promote_initial_admin skipped (run migrations first): %s", exc
            )


# ── Static files (Vite build output / vanilla fallback) ──────────────────────
app.mount("/", StaticFiles(directory="static", html=True), name="static")
