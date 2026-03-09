# storygen — OWASP Top 10 Security Assessment

**Date:** 2026-03-09
**Scope:** Full codebase review — FastAPI backend, React/TypeScript frontend, Docker infrastructure
**Mode tested:** Multi-user (DATABASE_URL set)
**Method:** White-box static analysis

---

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 5 |
| 🟡 Medium | 7 |
| 🔵 Low | 4 |
| ⚪ Info | 3 |

No critical vulnerabilities were found. The most impactful issues are: Gmail refresh tokens stored in plaintext, missing HTTP security headers (CSP / X-Frame-Options / HSTS), no server-side session invalidation on logout, subprocess stderr leaked verbatim to clients, and no security event logging.

---

## OWASP Top 10 Results

### ✅ A01 — Broken Access Control

**Status: MOSTLY PROTECTED — 2 findings**

#### MEDIUM — Unbounded `limit` parameter on `/api/admin/users`
**File:** `web/routers/admin.py` line 81
```python
async def list_users(..., limit: int = 50):
```
The `limit` query parameter has no maximum cap. An admin (or an attacker who has compromised an admin account) can pass `?limit=9999999`, causing the server to load all users into memory at once. This is a potential DoS vector against the application's own database.

**Remediation:** Add `limit: int = Query(default=50, le=500)` to cap the maximum page size.

---

#### LOW — Admin route guard uses `useEffect` (brief flash, server-side protected)
**File:** `frontend/src/pages/AdminPage.tsx` lines 28–31
```tsx
if (!me?.is_admin) { navigate("/", { replace: true }); return; }
```
The redirect happens after the component mounts and `useEffect` fires. A non-admin user navigating directly to `/admin` will briefly render the admin page skeleton before being redirected. The actual data endpoints (`/api/admin/*`) are correctly gated server-side by `Depends(require_admin)`, so no data is at risk — this is a UX defect only.

**Remediation:** Move the admin check into the `ProtectedRoute` component or a dedicated `AdminRoute` wrapper that prevents rendering entirely.

---

### ⚠️ A02 — Cryptographic Failures

**Status: 1 HIGH, 2 INFO findings**

#### HIGH — Gmail refresh tokens stored in plaintext
**File:** `web/db/models.py` line 30
```python
gmail_refresh_token: Mapped[str | None] = mapped_column(Text)
```
Gmail OAuth2 refresh tokens are stored directly in the `users` table as plain text. A database dump or SQL injection vulnerability would immediately expose all users' long-lived Gmail tokens, which can be used to send emails on their behalf indefinitely until they revoke access.

**Remediation:** Encrypt the token at rest using application-level encryption (e.g., `cryptography.fernet`) before persisting, and decrypt on read. The encryption key should be stored separately from the database (e.g., in the `SECRET_KEY` env var or a dedicated `REFRESH_TOKEN_KEY`).

---

#### INFO — Session cookie signed but not encrypted (user UUID visible)
**File:** `web/auth.py` line 41
```python
_signer = URLSafeTimedSerializer(SECRET_KEY, salt="session")
```
`URLSafeTimedSerializer` signs the payload but encodes it as base64 — the user's UUID is visible to anyone who holds the cookie. This is not a security risk by itself (UUIDs are non-sensitive opaque identifiers), but the cookie is not opaque.

**Remediation:** Acceptable as-is. If opacity is required, switch to `itsdangerous.TimestampSigner` with a server-side session store, or use `authlib`'s JWE for encrypted tokens.

---

#### INFO — HTTPS not enforced at the application layer
The application sets `Secure` cookies by default (`SECURE_COOKIES=true`) but relies on a reverse proxy for HTTPS termination and HTTP→HTTPS redirection. No HSTS header is emitted by the app.

**Remediation:** Add `Strict-Transport-Security: max-age=31536000; includeSubDomains` at the reverse proxy or via a FastAPI middleware. Document this requirement in the deployment guide.

---

### ✅ A03 — Injection

**Status: PROTECTED**

- **SQL Injection:** All queries use SQLAlchemy ORM with parameterized statements. No raw SQL strings. ✅
- **Command Injection:** `output_prefix` is sanitized to `[a-zA-Z0-9_-]` before use; subprocess is called with a list (no `shell=True`). ✅
- **Path Traversal (`/api/video`, `/api/send-email`):** Both endpoints resolve and check that the path stays inside `OUTPUT_DIR` using `str(path).startswith(output_root)`. ✅
- **Path Traversal (`/api/image/{filename}`):** Blocks `/`, `\\`, and `..` in the filename. ✅
- **Template/SSTI:** No template engines in use. ✅

---

### ⚠️ A04 — Insecure Design

**Status: 2 MEDIUM findings**

#### MEDIUM — No rate limiting on any endpoint
None of the endpoints — including auth (`/auth/google/callback`), video generation (`/api/generate`), email sending (`/api/send-email`), or admin operations — have rate limiting. An authenticated user could:
- Spam `/api/generate` to exhaust server CPU/disk
- Spam `/api/send-email` to abuse the Resend quota
- An admin could spam `/api/admin/users/{id}` delete

**Remediation:** Add `slowapi` (a FastAPI-compatible rate limiter) as middleware. Suggested limits: `/api/generate` — 10 req/min per user; `/api/send-email` — 5 req/hour per user; `/api/admin/*` — 100 req/min per admin.

---

#### MEDIUM — No CSRF token on state-changing endpoints (mitigated by `SameSite=lax`)
The application uses `SameSite=lax` cookies without explicit CSRF tokens. `SameSite=lax` blocks cross-site `fetch()` requests from including the cookie (because they are not top-level navigations), and FastAPI has no permissive CORS configured, so cross-origin API calls will be blocked by the browser's CORS pre-flight check.

**Effective risk: LOW** — the layered mitigations are sufficient for most threat models. However, `SameSite=lax` does not protect against requests originating from the same eTLD+1 (e.g., a compromised subdomain).

**Remediation:** Add `SameSite=strict` if cross-site linking to the app is not needed, or add an explicit `X-CSRF-Token` header check for all mutating endpoints.

---

### ⚠️ A05 — Security Misconfiguration

**Status: 2 HIGH, 2 MEDIUM findings**

#### HIGH — Missing HTTP security headers
FastAPI does not add security headers by default, and none are configured. The following are absent:

| Header | Risk if missing |
|--------|----------------|
| `Content-Security-Policy` | XSS payloads can load scripts from any origin |
| `X-Frame-Options: DENY` | Clickjacking attacks on admin operations |
| `X-Content-Type-Options: nosniff` | MIME-type sniffing |
| `Referrer-Policy: strict-origin-when-cross-origin` | URL leakage in Referer header |
| `Permissions-Policy` | Unnecessary browser feature access |
| `Strict-Transport-Security` | HTTPS downgrade attacks |

**Remediation:** Add `starlette-security-headers` or a custom middleware:
```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://lh3.googleusercontent.com; "
            "frame-ancestors 'none';"
        )
        return response
```

---

#### HIGH — Subprocess `stderr` returned verbatim to the client
**File:** `web/main.py` lines 144–148
```python
if result.returncode != 0:
    raise HTTPException(
        status_code=500,
        detail=result.stderr or "Video generation failed",
    )
```
If `generate.py` crashes, the full stderr output — which may contain filesystem paths, Python tracebacks, library versions, and internal system information — is returned to the client in the HTTP response body.

**Remediation:** Log `result.stderr` server-side and return only a generic message to the client:
```python
if result.returncode != 0:
    import logging
    logging.getLogger(__name__).error("generate.py failed: %s", result.stderr)
    raise HTTPException(status_code=500, detail="Video generation failed")
```

---

#### MEDIUM — Default PostgreSQL password in `docker-compose.yml`
**File:** `docker-compose.yml` line 90
```yaml
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-storygen}
```
If `POSTGRES_PASSWORD` is not set in `.env`, the database password defaults to `"storygen"`. A deployment that forgets to set this variable will have a weak, publicly-known default password.

**Remediation:** Remove the default fallback: use `${POSTGRES_PASSWORD}` (no `:-`) so compose fails loudly if the variable is unset. Add a pre-flight check in the deployment docs.

---

#### MEDIUM — `--reload` flag in production `web` service
**File:** `docker-compose.yml` line 21
```yaml
command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
`--reload` is a development-only flag. It spawns a file-watcher process, increases memory usage, and may expose internal file-watching behaviour. It should not be used in production.

**Remediation:** Move the production command to a `Dockerfile` `CMD` without `--reload`, and use the compose `command:` override only in a dev profile.

---

### ⚠️ A06 — Vulnerable and Outdated Components

**Status: 1 MEDIUM finding**

#### MEDIUM — `moviepy==1.0.3` pinned to a 5-year-old version; no automated CVE scanning
`moviepy==1.0.3` was released in 2020. All other backend dependencies use `>=` constraints (allowing security patches), but moviepy is pinned exactly. Additionally, no automated CVE/vulnerability scanner (`pip-audit`, `trivy`, `snyk`) is integrated into CI.

**Remediation:**
1. Test compatibility with `moviepy>=1.0.3` (or the latest `moviepy 2.x` series) and relax the pin.
2. Add `pip-audit` to the backend-test container CMD or a separate CI step:
   ```bash
   pip-audit --requirement requirements.txt
   ```

---

### ⚠️ A07 — Identification and Authentication Failures

**Status: 1 HIGH, 1 MEDIUM finding**

#### HIGH — No server-side session invalidation on logout
**File:** `web/routers/auth.py` lines 76–81
```python
@router.post("/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response
```
Logout only clears the cookie on the client. The signed token itself remains valid for its full 30-day lifetime. If an attacker exfiltrates a session cookie before the user logs out (via XSS, network interception, or device theft), they retain full access for up to 30 days with no way to revoke it server-side.

**Remediation:** Maintain a server-side token blocklist (e.g., a `sessions` table or Redis set storing invalidated token signatures). On each request in `get_current_user`, check whether the token's signature has been revoked. On logout, add the token to the blocklist with a TTL matching `SESSION_MAX_AGE`.

---

#### MEDIUM — 30-day session with no sliding expiry
`SESSION_MAX_AGE = 60 * 60 * 24 * 30` (30 days). Once issued, a session does not refresh on activity. A user who logs in and stays active will find their session suddenly expire after 30 days regardless of recent activity.

**Remediation:** Issue a new cookie (with a fresh timestamp) on each authenticated request, or implement a sliding window by re-signing the token with the current timestamp when the session is within the last 7 days of validity.

---

### ✅ A08 — Software and Data Integrity Failures

**Status: PROTECTED (with future note)**

No deserialization of untrusted data, no `pickle`, no `eval`. Config writes go through Pydantic-validated `BlockUpdate` models before being persisted.

**⚠️ Future risk — planned file upload endpoints:** The ROADMAP describes `POST /api/upload/image` and `POST /api/upload/music`. When implemented, these will need:
- MIME type validation (both Content-Type header and magic bytes)
- File extension allowlist (`.jpg`, `.png`, `.mp3`, `.m4a` only)
- File size limits (e.g., `python-multipart` `max_size`)
- Storage strictly inside the user's isolated `/storage/{user_id}/` directory

---

### ⚠️ A09 — Security Logging and Monitoring Failures

**Status: 1 HIGH finding**

#### HIGH — No security event logging
The application has no structured security logging. None of the following events are logged:

| Event | Why it matters |
|-------|----------------|
| Successful login | Detect account takeover |
| Failed auth (401/403) | Detect brute-force / enumeration |
| Admin operations (disable/delete) | Audit trail |
| Video generation triggered | Detect abuse |
| Email sends | Detect relay abuse |
| Path traversal attempts (blocked) | Detect active attacks |

The only logging in the codebase is a single `logging.warning` in `promote_initial_admin`.

**Remediation:** Add a `structlog` or standard-library logging call at key security boundaries:
```python
import logging
_sec_log = logging.getLogger("storygen.security")

# In get_current_user:
_sec_log.info("auth.success user_id=%s", user.id)

# In require_admin (on failure):
_sec_log.warning("authz.denied user_id=%s endpoint=%s", user.id, request.url.path)

# In delete_user:
_sec_log.warning("admin.delete_user actor=%s target=%s", admin.id, user_id)
```

---

### ✅ A10 — Server-Side Request Forgery (SSRF)

**Status: PROTECTED**

- The only outbound server-side HTTP calls are: Google's OIDC discovery endpoint (hardcoded URL) and the Resend API (hardcoded SDK call). Neither is influenced by user-supplied URLs. ✅
- `avatar_url` from Google OAuth is stored and served to the browser as an `<img>` `src` — the browser fetches it, not the server. ✅
- No URL-fetching utilities accept user-supplied URLs. ✅

---

## Findings Summary

| ID | Severity | OWASP | File | Issue |
|----|----------|-------|------|-------|
| S-01 | 🟠 HIGH | A02 | `web/db/models.py:30` | Gmail refresh tokens stored plaintext |
| S-02 | 🟠 HIGH | A05 | `web/main.py` | Missing security headers (CSP, X-Frame-Options, etc.) |
| S-03 | 🟠 HIGH | A05 | `web/main.py:144` | Subprocess `stderr` returned verbatim to client |
| S-04 | 🟠 HIGH | A07 | `web/routers/auth.py:76` | No server-side session invalidation on logout |
| S-05 | 🟠 HIGH | A09 | (entire backend) | No security event logging |
| S-06 | 🟡 MEDIUM | A01 | `web/routers/admin.py:81` | Unbounded `limit` param on user list |
| S-07 | 🟡 MEDIUM | A04 | (entire backend) | No rate limiting on any endpoint |
| S-08 | 🟡 MEDIUM | A04 | `web/routers/auth.py` | No CSRF tokens (mitigated by SameSite=lax) |
| S-09 | 🟡 MEDIUM | A05 | `docker-compose.yml:90` | Default weak PostgreSQL password |
| S-10 | 🟡 MEDIUM | A05 | `docker-compose.yml:21` | `--reload` flag in production web service |
| S-11 | 🟡 MEDIUM | A06 | `Dockerfile:14` | `moviepy==1.0.3` outdated; no CVE scanning |
| S-12 | 🟡 MEDIUM | A07 | `web/auth.py:39` | 30-day session, no sliding expiry |
| S-13 | 🔵 LOW | A01 | `frontend/.../AdminPage.tsx:28` | Admin guard via `useEffect` (flash, server-side protected) |
| S-14 | ⚪ INFO | A02 | `web/auth.py:41` | Session cookie signed but not encrypted |
| S-15 | ⚪ INFO | A02 | (deployment) | HTTPS not enforced at app layer |
| S-16 | ⚪ INFO | A07 | (roadmap) | File uploads will need validation when implemented |

---

## Prioritised Remediation Roadmap

---

### Sprint 1 — Quick wins (< 1 day total)

**Status: ✅ S-03, S-09 already resolved in multi-user refactor.**

---

#### S-02 — Add security headers middleware

**File:** `web/main.py` — add after `app = FastAPI()`

```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://lh3.googleusercontent.com; "
            "frame-ancestors 'none';"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

**Acceptance test** (`tests/test_security_headers.py`):
```python
@pytest.mark.asyncio
async def test_security_headers_present(client):
    resp = await client.get("/api/blocks")
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in resp.headers["content-security-policy"]
```

---

#### S-03 — Log stderr server-side; return generic error ✅ Already done

**File:** `web/main.py` (resolved during multi-user refactor)

The current code already does:
```python
_log.error("generate.py failed for user %s: %s", _auth.id, result.stderr)
raise HTTPException(500, "Video generation failed")
```

No further action required.

---

#### S-09 — Remove PostgreSQL default password ✅ Already done

**File:** `docker-compose.yml` (resolved during multi-user refactor)

Changed from `${POSTGRES_PASSWORD:-storygen}` to `${POSTGRES_PASSWORD}` — compose now fails loudly if the variable is unset.

---

#### S-06 — Cap `limit` parameter on `/api/admin/users`

**File:** `web/routers/admin.py` — change line 81

```python
# Before
limit: int = 50,

# After
from fastapi import Query
limit: int = Query(default=50, le=500),
```

**Acceptance test:**
```python
@pytest.mark.asyncio
async def test_list_users_limit_capped(admin_client):
    resp = await admin_client.get("/api/admin/users?limit=9999")
    assert resp.status_code == 422   # FastAPI validation error
```

---

### Sprint 2 — Auth hardening (1–2 days)

#### S-04 — DB-backed session blocklist for proper logout

**New Alembic migration:** `alembic/versions/0002_session_blocklist.py`
```python
def upgrade():
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String, primary_key=True),   # token signature hash
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])
```

**New model** (`web/db/models.py`):
```python
class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String, primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

**`web/auth.py`** — `get_current_user`:
```python
import hashlib
from datetime import datetime, timezone

async def get_current_user(session: ..., db: ...) -> User:
    if not session:
        raise HTTPException(401, "Not authenticated")
    # Check blocklist before decoding
    jti = hashlib.sha256(session.encode()).hexdigest()
    revoked = (await db.execute(
        select(RevokedToken).where(RevokedToken.jti == jti)
    )).scalar_one_or_none()
    if revoked:
        raise HTTPException(401, "Session revoked")
    ...
```

**`web/routers/auth.py`** — `logout`:
```python
from datetime import datetime, timezone

@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        jti = hashlib.sha256(token.encode()).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(seconds=SESSION_MAX_AGE)
        db.add(RevokedToken(jti=jti, expires_at=expires))
        await db.commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response
```

**Periodic cleanup** (startup event or cron):
```python
# Delete expired revocations
await db.execute(
    delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc))
)
```

**Acceptance test:**
```python
@pytest.mark.asyncio
async def test_logout_invalidates_session(client):
    # Logout should succeed
    resp = await client.post("/auth/logout")
    assert resp.status_code == 200
    # Subsequent request with the same session should fail (mocked blocklist hit)
```

---

#### S-05 — Security event logging

**File:** `web/auth.py` — add to `get_current_user`:
```python
_sec_log = logging.getLogger("storygen.security")

async def get_current_user(...) -> User:
    if not session:
        _sec_log.warning("auth.missing_cookie ip=%s", request.client.host)
        raise HTTPException(401, "Not authenticated")
    ...
    if not user:
        _sec_log.warning("auth.user_not_found token_uid=%s", user_id)
        raise HTTPException(401, "User not found")
    if not user.is_active:
        _sec_log.warning("auth.disabled_account user_id=%s", user.id)
        raise HTTPException(403, "Account disabled")
    _sec_log.info("auth.success user_id=%s", user.id)
    return user
```

**File:** `web/routers/admin.py` — add to `delete_user` and `patch_user`:
```python
_sec_log = logging.getLogger("storygen.security")

# In delete_user, after db.commit():
_sec_log.warning("admin.delete_user actor=%s target=%s email=%s",
                 admin.id, user_id, deleted_email)

# In patch_user, per notification:
_sec_log.warning("admin.patch_user actor=%s target=%s changes=%s",
                 admin.id, user_id, [n[0] for n in notifications])
```

**File:** `web/main.py` — add to `generate()` and `send_email()`:
```python
# On path traversal rejection:
_sec_log.warning("security.path_traversal user_id=%s filename=%s", _auth.id, req.filename)

# On successful generate:
_sec_log.info("generate.success user_id=%s filename=%s", _auth.id, filename)
```

**Acceptance test:**
```python
def test_security_logging_on_admin_delete(admin_client, caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="storygen.security"):
        # ... call delete endpoint
        assert "admin.delete_user" in caplog.text
```

---

### Sprint 3 — Encryption & rate limiting (2–3 days)

#### S-01 — Encrypt Gmail refresh tokens at rest

**`Dockerfile`** — add to pip install:
```
"cryptography>=42.0.0"
```

**New env var (`.env.example`):**
```
REFRESH_TOKEN_KEY=  # 32-byte URL-safe base64 key; generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**`web/db/models.py`** — encrypt/decrypt helpers:
```python
import os
from cryptography.fernet import Fernet

def _get_fernet() -> Fernet | None:
    key = os.environ.get("REFRESH_TOKEN_KEY", "")
    return Fernet(key.encode()) if key else None

def encrypt_token(plaintext: str | None) -> str | None:
    if not plaintext:
        return None
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode() if f else plaintext

def decrypt_token(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode() if f else ciphertext
```

**`web/routers/auth.py`** — encrypt on write, decrypt on read:
```python
from db.models import encrypt_token, decrypt_token

# On upsert:
user.gmail_refresh_token = encrypt_token(gmail_refresh_token)

# Where the token is used (Gmail send):
raw_token = decrypt_token(user.gmail_refresh_token)
```

**Acceptance test:**
```python
def test_token_roundtrip(monkeypatch):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("REFRESH_TOKEN_KEY", key)
    from db.models import encrypt_token, decrypt_token
    plaintext = "ya29.test-token"
    cipher = encrypt_token(plaintext)
    assert cipher != plaintext
    assert decrypt_token(cipher) == plaintext
```

---

#### S-07 — Rate limiting with `slowapi`

**`Dockerfile`** — add to pip install:
```
"slowapi>=0.1.9"
```

**`web/main.py`** — add limiter:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/generate")
@limiter.limit("10/minute")
async def generate(request: Request, ...):
    ...

@app.post("/api/send-email")
@limiter.limit("5/hour")
def send_email(request: Request, ...):
    ...
```

**Suggested limits:**

| Endpoint | Limit | Rationale |
|----------|-------|-----------|
| `POST /api/generate` | 10 req/min per IP | CPU-intensive; daily limit already guards DB |
| `POST /api/send-email` | 5 req/hour per IP | Prevent relay abuse |
| `GET /auth/google` | 20 req/min per IP | Prevent OAuth flow enumeration |
| `GET /api/admin/users` | 100 req/min per IP | Admin endpoints |

**Acceptance test:**
```python
@pytest.mark.asyncio
async def test_generate_rate_limited(client):
    payload = [...]
    # Exhaust the rate limit
    for _ in range(10):
        with patch("web.main.subprocess.run", return_value=_make_proc(0)):
            await client.post("/api/generate", json=payload)
    # 11th request should be rate-limited
    resp = await client.post("/api/generate", json=payload)
    assert resp.status_code == 429
```

---

### Sprint 4 — Dependencies & monitoring (1 day + ongoing)

#### S-11 — Upgrade moviepy; add `pip-audit` to CI

**`Dockerfile`** — relax pin and add audit:
```dockerfile
# Change:
"moviepy==1.0.3"
# To:
"moviepy>=1.0.3"
```

**`docker-compose.yml`** — backend-test CMD:
```yaml
command: >
  sh -c "pip-audit --no-deps --desc && pytest tests/ ..."
```

Or as a separate CI step:
```yaml
- name: Security audit
  run: docker run --rm storygen-backend pip-audit
```

**Acceptance:** `pip-audit` exits 0 (no known CVEs) in the test pipeline.

---

#### S-10 — Remove `--reload` from production service

**`docker-compose.yml`** — change web service command:
```yaml
# Development override (docker-compose.override.yml):
services:
  web:
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production (docker-compose.yml):
services:
  web:
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

Or move `--reload` to a `docker-compose.dev.yml` overlay that developers opt into with:
```bash
podman compose -f docker-compose.yml -f docker-compose.dev.yml up
```

**Acceptance:** Production compose file has no `--reload` in any service command.
