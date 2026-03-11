import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji

# No numpy, no moviepy — ffmpeg handles all video encoding directly.

CONFIG_PATH = "/assets/config.json"
FADE_DURATION = 1.0
IMAGES_DIR = "/assets/images"
ASSETS_DIR = "/assets"
OUTPUT_DIR = "/output"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def load_config(path):
    with open(path) as f:
        return json.load(f)


def render_frame(image_path, text, text_position, font_size, font_color, width, height, bw=False, align_center=False, center_x=False):
    """Return a PIL Image with the block's image + text overlay rendered."""
    img = Image.open(image_path).convert("RGB")
    scale = min(width / img.width, height / img.height)
    fitted = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    canvas.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
    img.close()
    img = canvas

    if bw:
        img = img.convert("L").convert("RGB")

    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except OSError:
        print(f"Warning: font not found at {FONT_PATH}, using default", file=sys.stderr)
        font = ImageFont.load_default()

    color = tuple(font_color) if isinstance(font_color, list) else font_color

    pad = 18
    radius = 14
    x, y = text_position[0], text_position[1]

    lines = text.split("\n")
    line_bboxes = [draw.textbbox((0, 0), line or " ", font=font) for line in lines]
    line_widths = [b[2] - b[0] for b in line_bboxes]
    left_bearings = [b[0] for b in line_bboxes]
    max_w = max(line_widths) if line_widths else 0

    y_bbox = draw.textbbox((0, y), text, font=font)
    top_y, bot_y = y_bbox[1], y_bbox[3]
    line_h = (bot_y - top_y) / len(lines)

    if center_x:
        x = (width - max_w) // 2

    rect = (x - pad, top_y - pad, x + max_w + pad, bot_y + pad)
    draw.rounded_rectangle(rect, radius=radius, fill=(0, 0, 0))

    with Pilmoji(img) as pilmoji:
        for idx, (line, lw, lb) in enumerate(zip(lines, line_widths, left_bearings)):
            base_x = x - lb
            lx = base_x + (max_w - lw) // 2 if align_center else base_x
            ly = y + int(idx * line_h)
            pilmoji.text((lx, ly), line, fill=color, font=font)

    return img


def build_clip_to_file(block, cfg, tmp_path):
    """Render one block and encode it directly to tmp_path via ffmpeg.

    Only PIL + pilmoji are needed — no numpy, no moviepy.
    """
    image_path = os.path.join(IMAGES_DIR, block["image"])
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    duration = block["end"] - block["start"]
    if duration <= 0:
        raise ValueError(f"Block has non-positive duration: {block}")

    img = render_frame(
        image_path=image_path,
        text=block.get("text", ""),
        text_position=block.get("text_position", [100, 900]),
        font_size=cfg["font_size"],
        font_color=cfg["font_color"],
        width=cfg["width"],
        height=cfg["height"],
        bw=block.get("bw", False),
        align_center=block.get("align_center", False),
        center_x=block.get("center_x", False),
    )

    png_fd, png_path = tempfile.mkstemp(suffix=".png", prefix="storygen_frame_")
    try:
        with os.fdopen(png_fd, "wb") as f:
            img.save(f, format="PNG")
        img.close()
        del img

        # Build ffmpeg fade filter
        vf_parts = []
        if block.get("fade_in", False):
            vf_parts.append(f"fade=type=in:start_time=0:duration={FADE_DURATION}")
        if block.get("fade_out", False):
            fade_start = max(0.0, duration - FADE_DURATION)
            vf_parts.append(f"fade=type=out:start_time={fade_start}:duration={FADE_DURATION}")

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(cfg["fps"]), "-i", png_path,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-r", str(cfg["fps"]),
        ]
        if vf_parts:
            cmd += ["-vf", ",".join(vf_parts)]
        cmd.append(tmp_path)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg segment failed:\n{result.stderr}")
    finally:
        try:
            os.unlink(png_path)
        except OSError:
            pass


def main():
    # argv[1] = output filename (optional, falls back to config prefix + timestamp)
    # argv[2] = config file path (optional, falls back to /assets/config.json)
    config_path = sys.argv[2] if len(sys.argv) > 2 else CONFIG_PATH
    cfg = load_config(config_path)

    tmp_segments = []
    concat_list_path = None

    try:
        # --- Phase 1: encode each block to a separate temp segment ---
        for i, block in enumerate(cfg["blocks"]):
            tmp_fd, tmp_path = tempfile.mkstemp(
                suffix=".mp4", prefix=f"storygen_seg{i}_"
            )
            os.close(tmp_fd)
            build_clip_to_file(block, cfg, tmp_path)
            tmp_segments.append(tmp_path)

        # --- Phase 2: build ffmpeg concat list ---
        concat_fd, concat_list_path = tempfile.mkstemp(
            suffix=".txt", prefix="storygen_concat_"
        )
        with os.fdopen(concat_fd, "w") as f:
            for p in tmp_segments:
                f.write(f"file '{p}'\n")

        # --- Phase 3: determine output path ---
        if len(sys.argv) > 1:
            filename = sys.argv[1]
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            filename = f"{cfg['output_prefix']}_{timestamp}.mp4"
        output_path = os.path.join(OUTPUT_DIR, filename)

        # --- Phase 4: ffmpeg final assembly ---
        music_file = cfg.get("music")
        if music_file:
            audio_path = os.path.join(ASSETS_DIR, music_file)
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Music file not found: {audio_path}")
            total_duration = sum(b["end"] - b["start"] for b in cfg["blocks"])
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_list_path,
                "-stream_loop", "-1", "-i", audio_path,
                "-map", "0:v:0", "-map", "1:a:0",
                "-fflags", "+genpts",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(total_duration),
                output_path,
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_list_path,
                "-fflags", "+genpts",
                "-c:v", "copy",
                output_path,
            ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed:\n{result.stderr}")

    finally:
        for p in tmp_segments:
            try:
                os.unlink(p)
            except OSError:
                pass
        if concat_list_path:
            try:
                os.unlink(concat_list_path)
            except OSError:
                pass

    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()
