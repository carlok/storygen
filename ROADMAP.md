# Roadmap — Public Multi-User Version

This document describes the architectural plan to evolve storygen from a personal local tool into a hosted, multi-user web application with Google OAuth2 login and per-user configuration stored in a database.

> **Status:** design only — not yet implemented.

---

## Goals

| Goal | Notes |
|------|-------|
| Multiple users, isolated data | Each user sees only their own images, music, configs, and videos |
| Google sign-in | No passwords; OAuth2 identity via Google |
| Gmail send (optional) | Users send from their own Gmail instead of a shared Resend account |
| No local file requirements | Images and music uploaded via the UI; no SSH or volume mounts needed |
| Horizontal scalability | Stateless API + external DB + object storage (S3/R2) |

---

## Authentication — Google OAuth2

**Library:** [`authlib`](https://docs.authlib.org/en/latest/integrations/fastapi.html) + `itsdangerous` for signed session cookies.

### Flow

```
Browser                FastAPI               Google
  │                      │                      │
  ├─GET /auth/google─────►                      │
  │                      ├─redirect OAuth URL──►│
  │◄─────────────────────────────────────────redirect
  ├─GET /auth/google/callback?code=xxx──────────►
  │                      │◄──── token exchange ─┤
  │                      ├─upsert user in DB    │
  │                      ├─set session cookie   │
  │◄─redirect to /────────                      │
```

### Scopes

- **Identity:** `openid email profile`
- **Gmail send (optional):** `https://www.googleapis.com/auth/gmail.send`

Store the Gmail refresh token in `users.gmail_refresh_token` so the user only needs to consent once.

### Session

- Short-lived JWT in an `HttpOnly` cookie (signed with `SECRET_KEY`)
- FastAPI dependency `current_user = Depends(get_current_user)` applied to all `/api/*` routes

---

## Database — Per-user config

**Stack:** PostgreSQL · SQLAlchemy (async) · Alembic migrations

### Schema

```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub    TEXT UNIQUE NOT NULL,       -- stable Google user ID
    email         TEXT NOT NULL,
    display_name  TEXT,
    avatar_url    TEXT,
    gmail_refresh_token TEXT,                 -- nullable; only if Gmail scope granted
    is_admin      BOOLEAN NOT NULL DEFAULT false,  -- access to /admin panel
    is_active     BOOLEAN NOT NULL DEFAULT true,   -- false = soft-disabled, blocks login
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE configs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    data       JSONB NOT NULL,               -- full config.json blob
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id)                         -- one config per user
);

CREATE TABLE jobs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    filename   TEXT NOT NULL,
    status     TEXT DEFAULT 'pending',       -- pending · running · done · error
    error      TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

The `configs.data` JSONB column stores the same structure as the current `config.json`, making migration trivial: a one-time import script reads the file and inserts a row.

---

## File Storage — Per-user isolation

### Local (phase 1)

```
/storage/
└── {user_id}/
    ├── images/
    ├── music/
    └── output/
```

All `IMAGES_DIR`, `MUSIC_DIR`, and `OUTPUT_DIR` paths in `generate.py` become runtime arguments scoped to the authenticated user.

### Cloud (phase 2)

Replace local paths with **S3 / Cloudflare R2**:

- Upload: presigned PUT URL → browser uploads directly to object storage
- Download/view: presigned GET URL (short-lived)
- `generate.py` downloads inputs from S3, runs, uploads result back

---

## New API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/auth/google` | Redirect to Google OAuth consent |
| `GET` | `/auth/google/callback` | Exchange code, upsert user, set cookie |
| `POST` | `/auth/logout` | Clear session cookie |
| `GET` | `/api/me` | Return current user info |
| `GET` | `/api/images` | List user's uploaded images |
| `POST` | `/api/upload/image` | Multipart upload → user's images dir |
| `POST` | `/api/upload/music` | Multipart upload → user's music dir |
| `GET` | `/admin` | Admin panel HTML — redirects non-admins to `/` |
| `GET` | `/api/admin/users` | List all users + job counts *(admin only)* |
| `GET` | `/api/admin/users/{id}` | Single user detail + last 10 jobs *(admin only)* |
| `PATCH` | `/api/admin/users/{id}` | Toggle `is_active` / `is_admin` *(admin only)* |
| `DELETE` | `/api/admin/users/{id}` | Hard-delete user and all their data *(admin only)* |
| `GET` | `/api/admin/stats` | Global totals: users, jobs, disk usage *(admin only)* |

All existing `/api/blocks`, `/api/generate`, `/api/send-email`, `/api/video` routes gain `current_user` scoping — no URL changes needed.

---

## Frontend changes

| Area | Change |
|------|--------|
| Login page | `/login` — Google sign-in button (OAuth redirect) |
| Header | User avatar + display name + logout link |
| Block card | Image drop zone replacing the static filename label — drag-and-drop or click to upload |
| Music | Upload field in a global settings panel |
| Config | Global settings panel (fps, resolution, font size, font colour) |

The core editing UI (tabs, canvas preview, sliders, toggles) stays unchanged.

---

## Infrastructure delta

### `docker-compose.yml` additions

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: storygen
      POSTGRES_USER: storygen
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  web:
    # existing — add DATABASE_URL to env_file
    ...

volumes:
  pgdata:
```

### Dockerfile additions (pip install)

```
authlib>=1.3.0
sqlalchemy[asyncio]>=2.0.0
alembic>=1.13.0
asyncpg>=0.29.0
python-multipart>=0.0.9
httpx>=0.27.0
itsdangerous>=2.1.0
```

### `.env` additions

```
GOOGLE_CLIENT_ID=xxxxxxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxx
DATABASE_URL=postgresql+asyncpg://storygen:password@db/storygen
SECRET_KEY=change-me-to-a-long-random-string
ADMIN_EMAIL=you@yourdomain.com
```

---

## Admin Panel

A lightweight admin layer gives one or more trusted users visibility over all accounts and the ability to perform basic management without touching the database directly.

### Access control — `require_admin` dependency

```python
async def require_admin(user = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(403, "Forbidden")
    return user
```

All `/api/admin/*` and `GET /admin` routes depend on this. Non-admin users get a 403 or are redirected to `/`.

### Admin API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/admin/users` | Paginated list of all users with job count per user |
| `GET` | `/api/admin/users/{id}` | Single user detail + their last 10 jobs |
| `PATCH` | `/api/admin/users/{id}` | Toggle `is_active` or `is_admin` flag |
| `DELETE` | `/api/admin/users/{id}` | Hard-delete user + cascade configs, jobs, and `/storage/{id}/` |
| `GET` | `/api/admin/stats` | Totals: users, videos generated, disk usage |

### Admin UI — `GET /admin`

A separate page (`web/static/admin.html`) styled identically to `index.html`:

| Element | Details |
|---------|---------|
| Stats bar | Total users · Total jobs generated · Storage used on disk |
| User table | Avatar · Email · Display name · Joined date · Job count · Active/Disabled badge · Admin badge |
| Row actions | **Disable / Enable** button (PATCH `is_active`) · **Make admin / Revoke** button (PATCH `is_admin`) · **Delete** button (confirm dialog → DELETE) |
| Access guard | JS checks `GET /api/me` on load; redirects to `/` if `is_admin` is false |

### First-admin seeding

Set `ADMIN_EMAIL` in `.env`. At application startup, `main.py` promotes that email to admin if the account exists and isn't already one — no manual SQL needed after the first Google login:

```python
@app.on_event("startup")
async def promote_initial_admin():
    admin_email = os.environ.get("ADMIN_EMAIL")
    if admin_email:
        await db.execute(
            "UPDATE users SET is_admin = true WHERE email = :e",
            {"e": admin_email},
        )
```

### `.env` / `.env.example` additions

```
ADMIN_EMAIL=you@yourdomain.com
```

---

## Migration path from personal → public

1. Run Alembic migration to create tables
2. Import existing `config.json` as the first user's config row
3. Move `assets/images/` and `assets/music/` into `/storage/{user_id}/`
4. Point `generate.py` paths at the new per-user directories
5. Wrap all routes with `Depends(current_user)`
6. Add login page and OAuth callback

The video generation pipeline (`generate.py`) requires **zero changes** — only the directory arguments change.
