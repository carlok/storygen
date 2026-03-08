# Story Video Generator

> Compose short MP4 videos from static images with text overlays — entirely inside a container, no installs on the host.

A personal (or multi-user) daily-video tool: load your photos, write captions in the browser, hit Generate, download or email the result. The container is a pure environment; all your files live on the host via volume mounts.

---

## Project structure

```
storygen/
├── Dockerfile                   # python:3.11-slim + ffmpeg + fonts + pip libs
├── docker-compose.yml           # profiles: cli · web · multi-user · test
├── pyproject.toml               # pytest config + coverage settings
├── .env                         # secrets (not committed — see .env.example)
├── src/
│   └── generate.py              # video pipeline (Pillow · pilmoji · moviepy)
├── web/
│   ├── main.py                  # FastAPI backend (personal + multi-user modes)
│   ├── auth.py                  # Google OAuth2 + signed session cookie
│   ├── db/
│   │   ├── engine.py            # async SQLAlchemy engine
│   │   └── models.py            # User · Config · Job ORM models
│   └── routers/
│       ├── auth.py              # /auth/google · /auth/google/callback · /auth/logout
│       └── admin.py             # /api/admin/* (users, stats)
├── frontend/                    # React 18 + Vite + TypeScript
│   ├── src/
│   │   ├── api/                 # typed fetch client (auth · blocks · admin)
│   │   ├── context/             # AuthContext · VideoContext
│   │   ├── components/          # Modal · Header · Footer
│   │   ├── features/            # BlockCard · CanvasPreview · AdminTable …
│   │   ├── pages/               # LoginPage · HomePage · AdminPage
│   │   └── styles/              # globals.css · admin.css
│   └── vite.config.ts           # outDir → ../web/static (FastAPI serves build)
├── alembic/                     # DB migrations
├── tests/                       # pytest backend test suite
├── assets/
│   ├── config.json              # your timeline (not committed — see .example)
│   ├── config.json.example
│   ├── images/                  # source photos
│   └── music/                   # background audio
└── output/                      # rendered MP4s land here
```

---

## Requirements

| Tool | Version |
|------|---------|
| [Podman](https://podman.io/getting-started/installation) | v4+ |
| [podman-compose](https://github.com/containers/podman-compose) | latest |
| Node.js *(frontend dev only)* | 20+ |

---

## Modes

| Mode | Description | Command |
|------|-------------|---------|
| **Personal** | Single user, no login required | `podman compose up web` |
| **Multi-user** | Google OAuth2, PostgreSQL, admin panel | `podman compose --profile multi-user up` |
| **Test** | Run backend + frontend test suites | `podman compose --profile test up` |
| **CLI** | Generate video without the web UI | `podman compose run --rm app` |

---

## First-time setup (personal mode)

```bash
# 1. Clone
git clone https://github.com/carlok/storygen.git && cd storygen

# 2. Build image
podman compose build

# 3. Configure secrets
cp .env.example .env
# → edit .env: fill in RESEND_API_KEY and RESEND_FROM

# 4. Create your config
cp assets/config.json.example assets/config.json
# → edit assets/config.json: set image filenames, durations, captions

# 5. Drop media in place
cp ~/photos/*.jpg assets/images/
cp ~/music/track.mp3 assets/music/

# 6. Start
podman compose up web
# Open http://localhost:8000
```

---

## Multi-user setup

```bash
# 1. Generate a strong secret key
python -c "import secrets; print(secrets.token_hex(32))"

# 2. Configure .env
SECRET_KEY=<output above>
DATABASE_URL=postgresql+asyncpg://storygen:yourpassword@db/storygen
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
ADMIN_EMAIL=you@yourdomain.com   # promoted to admin on first login

# 3. Start with the multi-user profile
podman compose --profile multi-user up

# 4. Run DB migrations (first time)
podman compose exec web alembic upgrade head
```

The `ADMIN_EMAIL` user is automatically promoted to admin on startup — no manual SQL needed.

---

## config.json reference

### Global fields

| Field | Type | Description |
|-------|------|-------------|
| `output_prefix` | string | Prefix for output filenames (`"video"` → `video_2026-03-07-12-00-00.mp4`) |
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

Music shorter than the total video duration is looped automatically.

---

## Web UI

```bash
podman compose up web        # personal mode
# or
podman compose --profile multi-user up   # multi-user mode
```

Open **http://localhost:8000**.

### Features

- **Tab per block** — switch between scenes without scrolling
- **Live canvas preview** — see the text pill on the actual image; drag to reposition
- **X / Y sliders** — fine-tune position numerically (range = full frame resolution)
- **Toggles** per block: Align center · Center X · B&W · Fade in · Fade out
- **Generate Video** — modal spinner blocks UI while rendering (~10–60 s)
- **Download Video** — direct link to the rendered MP4
- **Send Video** — email the MP4 via [Resend](https://resend.com)
- **Admin panel** *(multi-user only)* — `/admin`: user list, enable/disable, grant/revoke admin, usage stats

Changes are written back to `config.json` on each generate.

---

## Frontend development

```bash
cd frontend
npm install
npm run dev      # Vite dev server at :5173, proxies /api and /auth to :8000
npm test         # vitest + @testing-library with coverage
npm run build    # compiles into ../web/static — FastAPI serves it
```

---

## Running tests

### Backend

```bash
pip install pytest pytest-asyncio httpx pytest-cov
pytest --cov=web --cov-report=term-missing
```

### Frontend

```bash
cd frontend && npm test -- --coverage
```

### Both in Docker

```bash
podman compose --profile test up --abort-on-container-exit
# Coverage reports: coverage/backend/  and  coverage/frontend/
```

---

## Email setup (Resend)

1. Create a free account at [resend.com](https://resend.com)
2. Add and verify your sending domain
3. Generate an API key
4. Set in `.env`:
   ```
   RESEND_API_KEY=re_xxxxxxxxxxxx
   RESEND_FROM=noreply@yourdomain.com
   ```

> **Note:** email attachment size limits apply (~10 MB). For longer videos use the Download link instead.

---

## Daily workflow

1. `podman compose up web`
2. Open **http://localhost:8000**
3. Edit captions in each block tab
4. Drag text on the canvas preview to position
5. Click **Generate Video** and wait for the modal to clear
6. Click **Download Video** — or enter an email and click **Send Video**

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Container | Podman / Docker, python:3.11-slim |
| Video pipeline | moviepy 1.0.3, Pillow, pilmoji |
| Fonts | DejaVu Sans Bold, Noto Color Emoji |
| Backend | FastAPI + uvicorn |
| Auth | authlib (Google OAuth2) + itsdangerous (signed cookie) |
| Database | PostgreSQL 16 + SQLAlchemy async + Alembic |
| Frontend | React 18, Vite, TypeScript, React Router |
| Email | Resend API |
| Backend tests | pytest, pytest-asyncio, httpx, pytest-cov |
| Frontend tests | vitest, @testing-library/react, @vitest/coverage-v8 |
