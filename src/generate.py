import json
import os
import sys
from datetime import datetime
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

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
    img = Image.open(image_path).convert("RGB")
    scale = min(width / img.width, height / img.height)
    fitted = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    img = Image.new("RGB", (width, height), (0, 0, 0))
    img.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
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
    # visual width per line (b[2]-b[0] excludes left-bearing offset from draw pos)
    line_widths = [b[2] - b[0] for b in line_bboxes]
    # left bearing: pixels from draw position to actual visual left edge of glyph
    left_bearings = [b[0] for b in line_bboxes]
    max_w = max(line_widths) if line_widths else 0

    # vertical metrics (y-independent)
    y_bbox = draw.textbbox((0, y), text, font=font)
    top_y, bot_y = y_bbox[1], y_bbox[3]
    line_h = (bot_y - top_y) / len(lines)

    if center_x:
        x = (width - max_w) // 2

    rect = (x - pad, top_y - pad, x + max_w + pad, bot_y + pad)
    draw.rounded_rectangle(rect, radius=radius, fill=(0, 0, 0))

    with Pilmoji(img) as pilmoji:
        for idx, (line, lw, lb) in enumerate(zip(lines, line_widths, left_bearings)):
            # offset by -lb so visual left edge lands at x (symmetric padding)
            base_x = x - lb
            lx = base_x + (max_w - lw) // 2 if align_center else base_x
            ly = y + int(idx * line_h)
            pilmoji.text((lx, ly), line, fill=color, font=font)

    return np.array(img)


def build_clip(block, cfg):
    image_path = os.path.join(IMAGES_DIR, block["image"])
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    duration = block["end"] - block["start"]
    if duration <= 0:
        raise ValueError(f"Block has non-positive duration: {block}")

    frame = render_frame(
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

    clip = ImageClip(frame).set_duration(duration)
    if block.get("fade_in", False):
        clip = clip.fadein(FADE_DURATION)
    if block.get("fade_out", False):
        clip = clip.fadeout(FADE_DURATION)
    return clip


def main():
    # argv[1] = output filename (optional, falls back to config prefix + timestamp)
    # argv[2] = config file path (optional, falls back to /assets/config.json)
    config_path = sys.argv[2] if len(sys.argv) > 2 else CONFIG_PATH
    cfg = load_config(config_path)

    clips = []
    for block in cfg["blocks"]:
        clip = build_clip(block, cfg)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")

    music_file = cfg.get("music")
    if music_file:
        audio_path = os.path.join(ASSETS_DIR, music_file)
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Music file not found: {audio_path}")

        audio = AudioFileClip(audio_path)
        total_duration = video.duration
        if audio.duration < total_duration:
            audio = audio.audio_loop(duration=total_duration)
        audio = audio.subclip(0, total_duration)
        video = video.set_audio(audio)

    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        filename = f"{cfg['output_prefix']}_{timestamp}.mp4"
    output_path = os.path.join(OUTPUT_DIR, filename)
    video.write_videofile(output_path, fps=cfg["fps"], audio_codec="aac")
    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()
