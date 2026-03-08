# Story Video Generator

> Compose short MP4 videos from static images with text overlays — entirely inside a container, no installs on the host.

A personal (or multi-user) daily-video tool: load your photos, write captions in the browser, hit Generate, download or email the result. All your files live on the host via volume mounts — the container is a pure, reproducible environment.

---

## Project structure

```
storygen/
├── Dockerfile                   # backend: backend-base (prod) + backend-test stages
├── Dockerfile.frontend          # frontend: frontend-deps + frontend-dev + frontend-test
├── docker-compose.yml           # services for every profile (see table below)
├── pyproject.toml               # pytest config + coverage settings
├── .env                         # secrets — copy from .env.example, never commit
├── src/
│   └── generate.py              # video pipeline (Pillow · pilmoji · moviepy)
├── web/
│   ├── main.py                  # FastAPI app (personal + multi-user modes)
│   ├── auth.py                  # Google OAuth2 + signed session cookie
│   ├── db/
│   │   ├── engine.py            # async SQLAlchemy engine
│   │   └── models.py            # User · Config · Job ORM models
│   └── routers/
│       ├── auth.py              # /auth/google · /auth/google/callback · /auth/logout
│       └── admin.py             # /api/admin/* (users, stats, patch, delete)
├── frontend/                    # React 18 + Vite + TypeScript
│   ├── src/
│   │   ├── api/                 # typed fetch client (auth · blocks · admin)
│   │   ├── context/             # AuthContext · VideoContext
│   │   ├── components/          # Modal · Header · Footer
│   │   ├── features/            # BlockCard · CanvasPreview · AdminTable …
│   │   ├── pages/               # LoginPage · HomePage · AdminPage
│   │   └── styles/              # globals.css · admin.css
│   └── vite.config.ts           # outDir → ../web/static (FastAPI serves the build)
├── alembic/                     # async DB migrations
├── tests/                       # pytest backend test suite
├── assets/
│   ├── config.json              # your timeline — copy from config.json.example
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
| Node.js *(frontend dev only, on host)* | 20+ |

---

## Docker services & profiles

| Profile | Service | What it does |
|---------|---------|--------------|
| *(default)* | `web` | FastAPI backend on port 8000 |
| `cli` | `app` | One-shot video generation (no web UI) |
| `dev` | `frontend-dev` | Vite HMR dev server on port 5173 |
| `build` | `frontend-build` | Compiles React app → `web/static/` |
| `multi-user` | `db` | Production PostgreSQL |
| `test` | `db-test` | Ephemeral test PostgreSQL |
| `test` | `backend-test` | pytest + coverage |
| `test` | `frontend-test` | vitest + coverage |

---

## First-time setup — personal mode

```bash
# 1. Clone
git clone https://github.com/carlok/storygen.git && cd storygen

# 2. Build the backend image
podman compose build

# 3. Configure secrets
cp .env.example .env
# → edit .env: fill in RESEND_API_KEY and RESEND_FROM

# 4. Create your config
cp assets/config.json.example assets/config.json
# → edit config.json: image filenames, durations, captions

# 5. Drop media in place
cp ~/photos/*.jpg assets/images/
cp ~/music/track.mp3 assets/music/

# 6. Start
podman compose up web
# Open http://localhost:8000
```

---

## Multi-user setup

### Step 1 — Generate a secret key

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output — you will paste it into `SECRET_KEY` in your `.env`.

---

### Step 2 — Google OAuth2 setup

> You need a Google account. The whole setup takes ~5 minutes.

**2.1 — Create a project**

Go to [console.cloud.google.com](https://console.cloud.google.com).
Top-left dropdown → **New Project** → give it a name (e.g. `storygen`) → Create.

**2.2 — Configure the OAuth consent screen**

Left sidebar → *APIs & Services* → *OAuth consent screen*

| Field | Value |
|-------|-------|
| User type | **External** (any Google account) or **Internal** (your Google Workspace org only) |
| App name | `Storygen` (or anything) |
| User support email | your email |
| Developer contact email | your email |

Click *Save and Continue* → on the Scopes step, click **Add or remove scopes**, tick **email**, **profile**, **openid** → Update → Save and Continue.

On the *Test users* step (only required while the app is in **Testing** status): click **Add users** and add your own Google email. Save and Continue.

**2.3 — Create OAuth 2.0 credentials**

Left sidebar → *APIs & Services* → *Credentials* → **Create Credentials** → **OAuth 2.0 Client ID**

| Field | Value |
|-------|-------|
| Application type | **Web application** |
| Name | `Storygen web` |
| Authorized JavaScript origins | `http://localhost:8000` |
| Authorized redirect URIs | `http://localhost:8000/auth/google/callback` |

> For production add your domain too, e.g. `https://storygen.example.com/auth/google/callback`.
> The value here must match `OAUTH_REDIRECT_URI` in `.env` exactly.

Click **Create**. A dialog shows your **Client ID** (ends in `.apps.googleusercontent.com`) and **Client Secret** (starts with `GOCSPX-`). Copy both.

---

### Step 3 — Configure `.env`

```bash
cp .env.example .env
```

Uncomment and fill in the multi-user block:

```dotenv
SECRET_KEY=<output of step 1>

GOOGLE_CLIENT_ID=xxxxxxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxx

# Must match exactly what you entered in Google Cloud Console.
# Default already works for local dev — only change for production.
# OAUTH_REDIRECT_URI=http://localhost:8000/auth/google/callback

DATABASE_URL=postgresql+asyncpg://storygen:yourpassword@db/storygen
POSTGRES_PASSWORD=yourpassword

# This account is promoted to admin automatically on first login.
ADMIN_EMAIL=you@yourdomain.com

# Set to false when testing locally over plain HTTP.
SECURE_COOKIES=false
```

---

### Step 4 — Start and migrate

```bash
# Start backend + PostgreSQL
podman compose --profile multi-user up web db -d

# Run migrations (first time, or after schema changes)
podman compose exec web alembic upgrade head
```

Open **http://localhost:8000** → click **Sign in with Google** → the `ADMIN_EMAIL` account is promoted to admin automatically on first login.

---

### Admin panel

Visit **http://localhost:8000/admin** (admin accounts only) to:

- View all users, their status, and job count
- Enable / disable accounts
- Grant or revoke admin rights (cannot self-demote)
- Delete accounts (cannot self-delete)
- See aggregate stats (total users, jobs, disk usage)

---

## Frontend development

```bash
# Option A: native (fastest, requires Node 20 on host)
cd frontend
npm install
npm run dev      # Vite at :5173, proxies /api and /auth to :8000

# Option B: containerised (no Node.js needed on host)
podman compose build frontend-dev
podman compose --profile dev up frontend-dev
# Vite HMR at http://localhost:5173
# Source is volume-mounted — edits reload instantly, node_modules stay in the container
```

Build the production bundle (writes to `web/static/`):

```bash
# native
cd frontend && npm run build

# containerised
podman compose --profile build run --rm frontend-build
```

FastAPI's `StaticFiles(html=True)` mount serves the built React app automatically — no extra config needed.

---

## Running tests

### Backend

```bash
# native
pip install pytest pytest-asyncio httpx pytest-cov
pytest --cov=web --cov-report=term-missing

# containerised (multi-user mode against ephemeral PostgreSQL)
podman compose --profile test up backend-test db-test --abort-on-container-exit
```

### Frontend

```bash
# native
cd frontend && npm test -- --coverage

# containerised (source baked into image for deterministic CI)
podman compose --profile test up frontend-test --abort-on-container-exit
```

### Both at once

```bash
podman compose --profile test up --abort-on-container-exit
# Coverage reports:
#   coverage/backend/   (HTML — pytest-cov)
#   coverage/frontend/  (HTML — @vitest/coverage-v8)
```

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

Music shorter than total video duration is looped automatically.

---

## Web UI features

- **Tab per block** — switch between scenes without scrolling
- **Live canvas preview** — see the text pill on the actual image; drag to reposition
- **X / Y sliders** — fine-tune position numerically
- **Toggles** per block: Align center · Center X · B&W · Fade in · Fade out
- **Generate Video** — modal spinner while rendering (~10–60 s)
- **Download Video** — direct link to the rendered MP4
- **Send Video** — email the MP4 via Resend
- **Admin panel** *(multi-user only)* — user management and usage stats at `/admin`

---

## Email setup (Resend)

1. Create a free account at [resend.com](https://resend.com)
2. Add and verify your sending domain (or use `onboarding@resend.dev` for testing)
3. Generate an API key
4. Set `RESEND_API_KEY` and `RESEND_FROM` in `.env`

> Attachment size limits apply (~10 MB). Use the Download link for longer videos.

---

## Daily workflow

1. `podman compose up web`
2. Open **http://localhost:8000**
3. Edit captions in each block tab
4. Drag text on the canvas preview to reposition
5. Click **Generate Video** — wait for the modal to clear
6. Click **Download Video** — or enter an email and click **Send Video**

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Container | Podman / Docker, python:3.11-slim, node:20-alpine |
| Video pipeline | moviepy 1.0.3, Pillow, pilmoji |
| Fonts | DejaVu Sans Bold, Noto Color Emoji |
| Backend | FastAPI + uvicorn |
| Auth | authlib (Google OAuth2) + itsdangerous (signed cookie) |
| Database | PostgreSQL 16 + SQLAlchemy async + Alembic |
| Frontend | React 18, Vite, TypeScript, React Router |
| Email | Resend API |
| Backend tests | pytest, pytest-asyncio, httpx, pytest-cov |
| Frontend tests | vitest, @testing-library/react, @vitest/coverage-v8 |
