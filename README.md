# Story Video Generator

> Compose short MP4 videos from static images with text overlays — entirely inside a container, no installs on the host.

A personal daily-video tool: load your photos, write captions in the browser, hit Generate, download or email the result. The container is a pure environment; all your files live on the host via volume mounts.

---

## Project structure

```
storygen/
├── Dockerfile                   # python:3.11-slim + ffmpeg + fonts + pip libs
├── docker-compose.yml           # two services: web UI and CLI runner
├── .env                         # secrets (not committed — see .env.example)
├── src/
│   └── generate.py              # video pipeline (Pillow · pilmoji · moviepy)
├── web/
│   ├── main.py                  # FastAPI backend
│   └── static/
│       ├── index.html           # single-page UI shell
│       ├── style.css            # glassmorphism dark theme
│       └── app.js               # vanilla JS — canvas preview, API calls
├── assets/
│   ├── config.json              # your timeline (not committed — see .example)
│   ├── config.json.example      # template to copy and customise
│   ├── images/                  # source photos  (.gitkeep tracks the folder)
│   └── music/                   # background audio (.gitkeep tracks the folder)
└── output/                      # rendered MP4s land here (.gitkeep placeholder)
```

---

## Requirements

| Tool | Version |
|------|---------|
| [Podman](https://podman.io/getting-started/installation) | v4+ |
| [podman-compose](https://github.com/containers/podman-compose) | latest (`pip install podman-compose`) |

---

## First-time setup

```bash
# 1. Clone the repo
git clone https://github.com/youruser/storygen.git && cd storygen

# 2. Build the container image (once, or after Dockerfile changes)
podman compose build

# 3. Configure secrets
cp .env.example .env
# → edit .env: fill in RESEND_API_KEY and RESEND_FROM

# 4. Create your config
cp assets/config.json.example assets/config.json
# → edit assets/config.json: set your image filenames, durations, captions

# 5. Drop your media into place
cp ~/photos/*.jpg assets/images/
cp ~/music/track.mp3 assets/music/
```

---

## config.json reference

### Global fields

| Field | Type | Description |
|-------|------|-------------|
| `output_prefix` | string | Prefix for output filenames (e.g. `"video"` → `video_2026-03-07-12-00-00.mp4`) |
| `fps` | int | Frames per second (24 recommended) |
| `width` / `height` | int | Output resolution in pixels (e.g. 1080 × 1920 for vertical) |
| `font_size` | int | Text size in pixels |
| `font_color` | `[R, G, B]` | Text colour as RGB array |
| `music` | string | Path to audio relative to `assets/` — omit for silent video |

### Per-block fields

| Field | Type | Description |
|-------|------|-------------|
| `image` | string | Filename inside `assets/images/` |
| `start` / `end` | float | Time range in seconds (no gaps, no overlaps) |
| `text` | string | Caption — use `\n` for line breaks, emoji supported |
| `bw` | bool | Apply black & white filter |
| `fade_in` / `fade_out` | bool | 1-second fade at clip boundaries |
| `text_position` | `[x, y]` | Pixel coordinates of the text pill (top-left anchor) |
| `align_center` | bool | Center-align text lines within the pill |
| `center_x` | bool | Horizontally centre the entire pill on the frame |

Music shorter than total video duration is looped automatically.

---

## Web UI

```bash
podman compose up web
```

Open **http://localhost:8000**.

### Features

- **Tab per block** — switch between scenes without scrolling
- **Live canvas preview** — see the text pill on the actual image; drag to reposition
- **X / Y sliders** — fine-tune position numerically (range = full frame resolution)
- **Toggles** per block: Align center · Center X · B&W · Fade in · Fade out
- **Generate Video** — a modal spinner blocks the UI while rendering (~10–60 s depending on video length and machine speed)
- **Download Video** — direct link to the rendered MP4
- **Send Video** — email the MP4 via [Resend](https://resend.com); enter the recipient address and click Send

Changes are written back to `config.json` automatically on each generate.

---

## Email setup (Resend)

1. Create a free account at [resend.com](https://resend.com)
2. Add and verify your sending domain (or use Resend's shared `onboarding@resend.dev` for testing)
3. Generate an API key
4. Set in `.env`:
   ```
   RESEND_API_KEY=re_xxxxxxxxxxxx
   RESEND_FROM=noreply@yourdomain.com
   ```

> **Note:** email attachment size limits apply (~10 MB for most providers). For longer videos use the Download link instead.

---

## CLI usage

Run generation directly without the web UI:

```bash
podman compose run --rm app
```

Reads `assets/config.json` as-is and writes the video to `output/`.

---

## Daily workflow

1. `podman compose up web`
2. Open **http://localhost:8000**
3. Edit captions in each block tab
4. Drag text on the canvas preview to position
5. Click **Generate Video** and wait for the modal to clear
6. Click **Download Video** — or enter an email and click **Send Video**

---

## Adding or removing scenes

Edit `assets/config.json` directly (the web UI reflects changes on the next page load):

- **Add** a new object to the `blocks` array with `image`, `start`, `end`, and `text`
- **Remove** a block by deleting its entry
- Keep `start` of each block equal to `end` of the previous one — no gaps, no overlaps
- Rebuild is **not** required; config changes are picked up at generation time

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Container | Podman / Docker, python:3.11-slim |
| Video pipeline | moviepy 1.0.3, Pillow, pilmoji |
| Fonts | DejaVu Sans Bold, Noto Color Emoji |
| Backend | FastAPI + uvicorn |
| Frontend | Vanilla JS, Canvas API, CSS custom properties |
| Email | Resend API |
