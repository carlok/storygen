"""Helpers for asserting Content-Security-Policy headers in tests."""

from urllib.parse import urlparse


def csp_directive_sources(csp: str, directive: str) -> list[str]:
    """Return the space-separated source list for a CSP directive."""
    prefix = f"{directive} "
    for clause in csp.split(";"):
        clause = clause.strip()
        if clause.startswith(prefix):
            return clause[len(prefix) :].split()
    return []


def csp_allows_url(sources: list[str], url: str) -> bool:
    """Return True when *sources* includes an entry matching *url* (scheme + host)."""
    expected = urlparse(url)
    for src in sources:
        parsed = urlparse(src)
        if parsed.scheme == expected.scheme and parsed.netloc == expected.netloc:
            return True
    return False
