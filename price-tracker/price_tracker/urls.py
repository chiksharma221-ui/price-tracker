"""URL canonicalisation, so the same listing is recognised whether it arrives
from the dashboard, the CLI or the Chrome extension (which sees URLs full of
tracking parameters and SEO slugs)."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_AMAZON_ASIN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})", re.I)


def canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.").removeprefix("m.")

    if "amazon." in host:
        match = _AMAZON_ASIN.search(parsed.path)
        if match:
            return f"https://{host}/dp/{match.group(1).upper()}"

    if "flipkart." in host:
        pid = parse_qs(parsed.query).get("pid")
        item = re.search(r"/p/(itm[0-9a-z]+)", parsed.path, re.I)
        if item:
            suffix = f"?pid={pid[0]}" if pid else ""
            return f"https://{host}/p/{item.group(1).lower()}{suffix}"

    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme or 'https'}://{host}{path}"
