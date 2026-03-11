# Pre-production sweep — implementation plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close 12 pre-production gaps across security, image size, performance, and UX before first public deployment.

**Architecture:** All backend changes land in `web/main.py` (middleware additions + one endpoint fix). Dockerfile loses two packages. Frontend changes touch `globals.css`, `index.html`, two component files, and one new `ErrorBoundary` component. No DB migration needed.

**Tech Stack:** FastAPI + Starlette middleware, Pillow/Pilmoji, React 18, Vitest, pytest-asyncio.

---

## Task 1 — Security: CSP header + path-traversal guard

**Files:**
- Modify: `web/main.py` (SecurityHeadersMiddleware, get_image endpoint, middleware stack)
- Modify: `tests/test_security.py` (new file)

### Step 1 — Write failing tests

Create `tests/test_security.py`:

```python
"""Tests for security headers and endpoint hardening."""
import pytest
from httpx import ASGITransport, AsyncClient

from web.main import app


@pytest.fixture
async def anon_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_csp_header_present(client):
    resp = await client.get("/health")
    assert "content-security-policy" in resp.headers


async def test_csp_allows_self_scripts(client):
    csp = resp = (await client.get("/health")).headers["content-security-policy"]
    assert "script-src 'self'" in csp


async def test_csp_allows_google_fonts(client):
    csp = (await client.get("/health")).headers["content-security-policy"]
    assert "https://fonts.googleapis.com" in csp
    assert "https://fonts.gstatic.com" in csp


async def test_csp_allows_google_avatars(client):
    csp = (await client.get("/health")).headers["content-security-policy"]
    assert "https://lh3.googleusercontent.com" in csp


async def test_image_path_traversal_rejected(client):
    resp = await client.get("/api/image/../../../etc/passwd")
    assert resp.status_code in (400, 404)


async def test_image_path_traversal_dotdot_rejected(client):
    resp = await client.get("/api/image/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (400, 404)
```

### Step 2 — Run tests to verify they fail

```bash
podman compose --profile test run --rm backend-test 2>&1 | grep -E "PASSED|FAILED|ERROR|test_security"
```

Expected: all `test_security` tests FAILED.

### Step 3 — Implement: add CSP to SecurityHeadersMiddleware

In `web/main.py`, inside `SecurityHeadersMiddleware.dispatch`, add **after** the existing headers:

```python
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://lh3.googleusercontent.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
```

(`'unsafe-inline'` in style-src is required because React renders inline `style={...}` attributes.)

### Step 4 — Implement: harden path-traversal guard in get_image

Replace the string-check guard (lines ~372-377) with a resolve-based check:

```python
@app.get("/api/image/{filename}")
def get_image(filename: str, _auth: User = Depends(_auth_dep)):
    _images_root = Path("/assets/images").resolve()
    try:
        safe = (_images_root / filename).resolve()
    except Exception:
        raise HTTPException(400, "Invalid filename")
    if not safe.is_relative_to(_images_root):
        raise HTTPException(400, "Invalid filename")
    if not safe.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(path=str(safe))
```

### Step 5 — Run tests to verify they pass

```bash
podman compose --profile test run --rm backend-test 2>&1 | grep -E "PASSED|FAILED|ERROR|test_security"
```

Expected: all 6 `test_security` tests PASSED.

### Step 6 — Commit

```bash
git add web/main.py tests/test_security.py
git commit -m "fix(security): add CSP header and harden image path-traversal guard"
```

---

## Task 2 — Cleanup: Dockerfile, dead CSS, fix status.success colour

**Files:**
- Modify: `Dockerfile` (remove two pip packages)
- Modify: `frontend/src/styles/globals.css` (delete dead rules, add missing rule)

No new tests. Existing 35 backend + 45 frontend tests must still pass.

### Step 1 — Remove moviepy + numpy from Dockerfile

In `Dockerfile`, inside the `pip install` block, delete these two lines:

```
    "moviepy==1.0.3" \
    "numpy>=1.24.0" \
```

Neither is imported anywhere (`generate.py` was refactored to call ffmpeg directly).

### Step 2 — Remove dead CSS from globals.css

Delete the following CSS blocks entirely from `frontend/src/styles/globals.css`:

- `@keyframes spin { … }` (only used by removed modal)
- `input[type="email"] { … }` and its `:focus` rule
- `.email-row { … }`
- `.btn-send { … }` and all its pseudo-class variants
- `.email-status { … }`, `.email-status.error { … }`, `.email-status.success { … }`
- `.download-link { … }`, `.download-link.visible { … }`, `.download-link:hover { … }`
- `.modal-overlay { … }`
- `.modal-box { … }`
- `.modal-spinner { … }`
- `.modal-msg { … }`

### Step 3 — Fix missing .status.success rule (bug: success shows as grey)

`ActionsBar` applies `className="status success"` on success, but only `.status.error` is styled green. Add immediately after `.status.error`:

```css
.status.success { color: var(--green); }
```

### Step 4 — Verify backend tests still pass (Dockerfile rebuild)

```bash
podman compose --profile test run --build --rm backend-test 2>&1 | tail -5
```

Expected: `35 passed`.

### Step 5 — Commit

```bash
git add Dockerfile frontend/src/styles/globals.css
git commit -m "chore: remove moviepy/numpy from image, purge dead CSS, fix status.success colour"
```

---

## Task 3 — Performance: GZip + immutable cache headers for hashed assets

**Files:**
- Modify: `web/main.py` (two new middlewares, adjust middleware stack order)
- Modify: `tests/test_security.py` (add cache and gzip tests)

### Step 1 — Write failing tests

Append to `tests/test_security.py`:

```python
async def test_gzip_compresses_json_response(client):
    """API responses should be gzip-compressed when the client requests it."""
    resp = await client.get("/health", headers={"Accept-Encoding": "gzip"})
    assert resp.headers.get("content-encoding") == "gzip"


async def test_health_not_cached(client):
    """Non-asset responses must not get the immutable cache header."""
    resp = await client.get("/health")
    cc = resp.headers.get("cache-control", "")
    assert "immutable" not in cc
```

### Step 2 — Run tests to verify they fail

```bash
podman compose --profile test run --rm backend-test 2>&1 | grep -E "test_gzip|test_health_not_cached"
```

Expected: both FAILED.

### Step 3 — Implement: add GZipMiddleware and StaticCacheMiddleware

At the top of `web/main.py`, add to imports:

```python
from fastapi.middleware.gzip import GZipMiddleware
```

After `SecurityHeadersMiddleware` class definition, add:

```python
class StaticCacheMiddleware(BaseHTTPMiddleware):
    """Add long-lived immutable cache headers to Vite's hashed asset bundles."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
```

Then replace the two existing `add_middleware` lines with the full ordered stack:

```python
# Middleware order: innermost (first added) → outermost (last added).
# Request flows outermost→innermost; response flows innermost→outermost.
# GZip is outermost so it compresses the fully-formed response last.
app.add_middleware(SecurityHeadersMiddleware)              # sets security + CSP headers
app.add_middleware(StaticCacheMiddleware)                  # immutable cache for /assets/*
app.add_middleware(SessionMiddleware, secret_key=_SECRET_KEY)  # OAuth CSRF state
app.add_middleware(GZipMiddleware, minimum_size=500)       # outermost: compress response
```

### Step 4 — Run tests to verify they pass

```bash
podman compose --profile test run --rm backend-test 2>&1 | tail -8
```

Expected: all tests pass (count should now be 37 with the 2 new ones).

### Step 5 — Commit

```bash
git add web/main.py tests/test_security.py
git commit -m "perf: GZip middleware + immutable cache headers for hashed Vite assets"
```

---

## Task 4 — UX: favicon + meta description

**Files:**
- Modify: `frontend/index.html`

No new tests. Rebuild and visually confirm.

### Step 1 — Add favicon and meta description to index.html

In `frontend/index.html`, inside `<head>`, add two lines after `<meta name="viewport" ...>`:

```html
    <meta name="description" content="Generate MP4 story videos from images and text." />
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎬</text></svg>" />
```

### Step 2 — Rebuild frontend and verify

```bash
podman compose --profile build run --rm frontend-build 2>&1 | tail -5
```

Expected: clean build, no TypeScript errors.

### Step 3 — Commit

```bash
git add frontend/index.html web/static/index.html web/static/assets/
git commit -m "feat(ux): add emoji favicon and meta description"
```

---

## Task 5 — UX: auto-dismiss success, Ctrl+Enter shortcut, ErrorBoundary

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`
- Create: `frontend/src/components/ErrorBoundary.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/__tests__/ErrorBoundary.test.tsx` (new file)

### Step 1 — Write failing tests

Create `frontend/src/__tests__/ErrorBoundary.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ErrorBoundary } from "@/components/ErrorBoundary";

function Bomb() {
  throw new Error("test explosion");
}

describe("ErrorBoundary", () => {
  it("renders fallback when a child throws", () => {
    // suppress console.error noise from React's error boundary reporting
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    );
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    spy.mockRestore();
  });

  it("renders children normally when no error", () => {
    render(<ErrorBoundary><p>all good</p></ErrorBoundary>);
    expect(screen.getByText("all good")).toBeInTheDocument();
  });
});
```

### Step 2 — Run tests to verify they fail

```bash
podman compose --profile test run --rm frontend-test 2>&1 | grep -E "ErrorBoundary|FAIL"
```

Expected: FAIL with "Cannot find module '@/components/ErrorBoundary'".

### Step 3 — Implement ErrorBoundary component

Create `frontend/src/components/ErrorBoundary.tsx`:

```tsx
import { Component, ReactNode } from "react";

interface Props { children: ReactNode; }
interface State { hasError: boolean; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: "2rem", textAlign: "center", color: "var(--red)" }}>
          <p>Something went wrong. Please refresh the page.</p>
        </div>
      );
    }
    return this.props.children;
  }
}
```

### Step 4 — Wrap the app in main.tsx

In `frontend/src/main.tsx`, import ErrorBoundary and wrap:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider }  from "@/context/AuthContext";
import { VideoProvider } from "@/context/VideoContext";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { App } from "./App";
import "@/styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <VideoProvider>
            <App />
          </VideoProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
);
```

### Step 5 — Run frontend tests to verify ErrorBoundary passes

```bash
podman compose --profile test run --rm frontend-test 2>&1 | grep -E "ErrorBoundary|Tests"
```

Expected: `ErrorBoundary` tests PASSED.

### Step 6 — Implement auto-dismiss and Ctrl+Enter in HomePage

In `frontend/src/pages/HomePage.tsx`, add these two `useEffect` hooks inside the component (after the existing state declarations):

```tsx
// Auto-dismiss success message after 4 s
useEffect(() => {
  if (status?.type !== "success") return;
  const id = setTimeout(() => setStatus(null), 4000);
  return () => clearTimeout(id);
}, [status]);

// Ctrl+Enter (or Cmd+Enter on Mac) triggers generate
useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !generating) {
      handleGenerate();
    }
  };
  window.addEventListener("keydown", handler);
  return () => window.removeEventListener("keydown", handler);
}, [generating]);  // eslint-disable-line react-hooks/exhaustive-deps
```

### Step 7 — Final build + full test run

```bash
podman compose --profile test run --rm backend-test 2>&1 | tail -4
podman compose --profile test run --rm frontend-test 2>&1 | tail -4
podman compose --profile build run --rm frontend-build 2>&1 | tail -5
```

Expected: all backend tests pass, all frontend tests pass, build clean.

### Step 8 — Commit

```bash
git add frontend/src/components/ErrorBoundary.tsx \
        frontend/src/main.tsx \
        frontend/src/pages/HomePage.tsx \
        frontend/src/__tests__/ErrorBoundary.test.tsx \
        web/static/index.html web/static/assets/
git commit -m "feat(ux): auto-dismiss success status, Ctrl+Enter shortcut, ErrorBoundary"
```

---

## Final push

```bash
git push origin main
```
