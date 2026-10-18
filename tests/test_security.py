"""Tests for security headers and endpoint hardening."""

from tests.csp_helpers import csp_allows_url, csp_directive_sources


async def test_csp_header_present(client):
    resp = await client.get("/health")
    assert "content-security-policy" in resp.headers


async def test_csp_allows_self_scripts(client):
    csp = (await client.get("/health")).headers["content-security-policy"]
    assert "script-src 'self'" in csp


async def test_csp_allows_google_fonts(client):
    csp = (await client.get("/health")).headers["content-security-policy"]
    style_src = csp_directive_sources(csp, "style-src")
    font_src = csp_directive_sources(csp, "font-src")
    assert csp_allows_url(style_src, "https://fonts.googleapis.com")
    assert csp_allows_url(font_src, "https://fonts.gstatic.com")


async def test_csp_allows_google_avatars(client):
    csp = (await client.get("/health")).headers["content-security-policy"]
    img_src = csp_directive_sources(csp, "img-src")
    assert csp_allows_url(img_src, "https://lh3.googleusercontent.com")


async def test_image_path_traversal_rejected(client):
    resp = await client.get("/api/image/../../../etc/passwd")
    assert resp.status_code == 400


async def test_image_path_traversal_dotdot_rejected(client):
    resp = await client.get("/api/image/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code == 400


async def test_csp_allows_self_connect(client):
    csp = (await client.get("/health")).headers["content-security-policy"]
    assert "connect-src 'self'" in csp


async def test_gzip_compresses_json_response(client):
    """API responses over 500 bytes should be gzip-compressed when requested."""
    resp = await client.get("/api/blocks", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"


async def test_health_not_cached(client):
    """Non-asset responses must not get the immutable cache header."""
    resp = await client.get("/health")
    cc = resp.headers.get("cache-control", "")
    assert "immutable" not in cc
