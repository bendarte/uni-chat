from typing import Optional
from urllib.parse import urlparse, urlunparse

DISALLOWED_HOST_SUBSTRINGS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "x.com",
    "twitter.com",
}


def normalize_source_url(url: Optional[str]) -> str:
    if not url:
        return ""
    cleaned = url.strip()
    try:
        parsed = urlparse(cleaned)
    except Exception:
        return cleaned

    if parsed.scheme == "http" and parsed.netloc:
        return urlunparse(parsed._replace(scheme="https"))
    return cleaned


def is_valid_source_url(url: Optional[str]) -> bool:
    cleaned = normalize_source_url(url)
    if not cleaned:
        return False

    try:
        parsed = urlparse(cleaned)
    except Exception:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False

    host = parsed.netloc.lower()
    if any(blocked in host for blocked in DISALLOWED_HOST_SUBSTRINGS):
        return False

    return True
