from __future__ import annotations

import re
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


def normalize_image_url(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    url = raw.strip()
    if not url:
        return None
    lowered = url.casefold()
    if lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return url
    if "assets.tcgdex.net" not in lowered:
        return url
    if lowered.endswith("/high") or lowered.endswith("/low"):
        return f"{url}.webp"
    return f"{url}/high.webp"


def image_from_card_page(card_url: Any) -> str | None:
    if not isinstance(card_url, str):
        return None
    url = card_url.strip()
    if not url:
        return None
    try:
        with urlopen(url, timeout=8) as resp:  # nosec B310 - read-only public card pages
            html = resp.read().decode("utf-8", errors="ignore")
    except (TimeoutError, URLError, ValueError):
        return None

    patterns = [
        r"<meta[^>]+property=[\\\"']og:image[\\\"'][^>]+content=[\\\"']([^\\\"']+)[\\\"']",
        r"<meta[^>]+content=[\\\"']([^\\\"']+)[\\\"'][^>]+property=[\\\"']og:image[\\\"']",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if not match:
            continue
        found = match.group(1).strip()
        if found.startswith("//"):
            return f"https:{found}"
        if found.startswith("http://") or found.startswith("https://"):
            return found
    return None


def resolve_card_image(
    image_url: Any,
    card_url: Any,
    cache: dict[str, str | None],
) -> str | None:
    normalized = normalize_image_url(image_url)
    page = str(card_url or "").strip()
    if not page:
        return normalized

    if page not in cache:
        cache[page] = image_from_card_page(page)
    fallback = cache.get(page)
    if fallback and isinstance(normalized, str) and "assets.tcgdex.net" in normalized.casefold():
        return fallback
    if fallback and not normalized:
        return fallback
    return normalized
