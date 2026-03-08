import base64
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import resend

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

CONFIG_PATH = Path("/assets/config.json")
OUTPUT_DIR = Path("/output")
GENERATE_SCRIPT = Path("/src/generate.py")

app = FastAPI()


def read_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def write_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


@app.get("/api/blocks")
def get_blocks():
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
def generate(updates: List[BlockUpdate]):
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

    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    filename = f"{cfg['output_prefix']}_{timestamp}.mp4"

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
def get_image(filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    image_path = Path("/assets/images") / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path=str(image_path))


@app.get("/api/video")
def get_video(name: str = Query(..., description="Filename returned by /api/generate")):
    video_path = OUTPUT_DIR / name
    if not video_path.exists() or not video_path.suffix == ".mp4":
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(path=str(video_path), media_type="video/mp4", filename=name)


class EmailRequest(BaseModel):
    to: str
    filename: str


@app.post("/api/send-email")
def send_email(req: EmailRequest):
    video_path = OUTPUT_DIR / req.filename
    if not video_path.exists() or video_path.suffix != ".mp4":
        raise HTTPException(status_code=404, detail="Video not found")

    api_key = os.environ.get("RESEND_API_KEY", "")
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


app.mount("/", StaticFiles(directory="static", html=True), name="static")
