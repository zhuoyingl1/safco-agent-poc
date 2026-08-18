from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    clean_path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc, clean_path, "", ""))


def is_safco_product_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.netloc.endswith("safcodental.com") and parts.path.startswith("/product/")

