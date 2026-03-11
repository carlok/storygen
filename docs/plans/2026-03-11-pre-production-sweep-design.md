# Pre-production sweep — design doc

**Date:** 2026-03-11
**Scope:** security hardening, image cleanup, perf tuning, UX/UI polish
**Out of scope:** job history page, status-polling page

---

## Context

The app is a multi-user FastAPI + React SPA deployed via Podman volume mounts (dev) and
Dockerfile.prod (Railway / VPS). Background video generation queues work via FastAPI
`BackgroundTasks`; completed videos are emailed as attachments.

---

## Items

### Security

**S1 — Content-Security-Policy**
`SecurityHeadersMiddleware` currently sets `X-Frame-Options`, `X-Content-Type-Options`,
`Referrer-Policy`, `Permissions-Policy`, `HSTS`. CSP is missing.

The app loads Inter from Google Fonts CDN (`fonts.googleapis.com` / `fonts.gstatic.com`)
and serves Google avatar images (`lh3.googleusercontent.com`). CSP must allow these plus
the React-generated inline `style=` attributes.

Target header:
```
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
  font-src 'self' https://fonts.gstatic.com;
  img-src 'self' data: https://lh3.googleusercontent.com;
  connect-src 'self';
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
```

`'unsafe-inline'` in `style-src` is required because React renders inline `style={...}`
attributes on DOM elements.

**S2 — `/api/image` path-traversal guard**
Current guard checks for `/`, `\\`, `..` in the filename string. Replace with:
```python
safe = (Path("/assets/images") / filename).resolve()
if not safe.is_relative_to(Path("/assets/images").resolve()):
    raise HTTPException(400, "Invalid filename")
```
This is immune to null-byte, Unicode normalisation, and any encoding tricks.

---

### Cleanup / Image size

**C1 — Remove moviepy + numpy from Dockerfile**
`generate.py` was refactored to use ffmpeg directly; `moviepy==1.0.3` and `numpy>=1.24.0`
are no longer imported. Remove from the `pip install` line in `Dockerfile`.
Estimated image size saving: ~200 MB.

**C2 — Dead CSS**
The email/download/modal UI was removed but its CSS remains in `globals.css`.
Delete: `.email-row`, `input[type="email"]`, `.btn-send`, `.email-status.*`,
`.download-link.*`, `.modal-overlay`, `.modal-box`, `.modal-spinner`, `.modal-msg`,
`@keyframes spin`.

**C3 — Missing `.status.success` rule (bug)**
`ActionsBar` sets `className="status success"` on success but the CSS only defines
`.status` (muted grey) and `.status.error` (red). Success messages appear grey.
Add `.status.success { color: var(--green); }`.

---

### Performance / Tuning

**P1 — GZip middleware**
Add `GZipMiddleware(minimum_size=500)` to the FastAPI app. Compresses API JSON responses
and the SPA HTML. Negligible CPU cost; significant bandwidth saving on slow connections.

**P2 — Immutable cache headers for hashed assets**
Vite outputs content-hashed filenames (`index-DXBhaYu5.css`). Add a middleware that
sets `Cache-Control: public, max-age=31536000, immutable` for any response whose path
starts with `/assets/` (the Vite bundle output). The SPA `index.html` keeps
`Cache-Control: no-cache, must-revalidate`.

---

### UX / UI

**U1 — Favicon**
Add an SVG emoji favicon to `index.html`. No image file needed:
```html
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎬</text></svg>">
```

**U2 — `<meta name="description">`**
Add `<meta name="description" content="Generate MP4 story videos from images and text.">`.

**U3 — Auto-dismiss success status**
In `HomePage`, add a `useEffect` that clears the status after 4 s when `status.type === "success"`.
Error messages stay until the user acts.

**U4 — Ctrl+Enter shortcut**
In `HomePage`, add a `keydown` listener (attached to `window`, removed on unmount) that
calls `handleGenerate()` when `e.key === "Enter" && (e.ctrlKey || e.metaKey)` and the
button is not disabled.

**U5 — React `ErrorBoundary`**
Add a minimal `ErrorBoundary` class component in `src/components/ErrorBoundary.tsx`.
Wrap the `RouterProvider` in `main.tsx`. Catches unhandled render errors and shows a
fallback "Something went wrong" message instead of a blank screen.

---

## Approach

Sequential, one commit per layer:

1. `fix(security): CSP header + path-traversal guard`
2. `chore: remove dead moviepy/numpy from Dockerfile, purge dead CSS, fix status.success colour`
3. `perf: GZip middleware + immutable cache headers for hashed assets`
4. `feat(ux): favicon, meta description, auto-dismiss, Ctrl+Enter shortcut, ErrorBoundary`

Each commit is independently deployable and reviewable.

---

## Files changed

| File | Changes |
|------|---------|
| `web/main.py` | SecurityHeadersMiddleware CSP + cache middleware + GZipMiddleware + path-traversal fix |
| `Dockerfile` | Remove moviepy, numpy from pip install |
| `frontend/src/styles/globals.css` | Remove dead CSS blocks, add `.status.success` |
| `frontend/index.html` | Favicon, meta description |
| `frontend/src/pages/HomePage.tsx` | Auto-dismiss useEffect, Ctrl+Enter listener |
| `frontend/src/components/ErrorBoundary.tsx` | New file |
| `frontend/src/main.tsx` | Wrap app in ErrorBoundary |
