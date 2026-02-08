"""Remote source adapters for Phase 1 data ingestion."""

from __future__ import annotations

import html
import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx

TCGDEX_POCKET_SERIES_URL = "https://api.tcgdex.net/v2/en/series/tcgp"
TCGDEX_SET_URL_TEMPLATE = "https://api.tcgdex.net/v2/en/sets/{set_id}"
TCGDEX_CARD_URL_TEMPLATE = "https://api.tcgdex.net/v2/en/cards/{card_id}"
LIMITLESS_POCKET_DECKS_URL = "https://play.limitlesstcg.com/decks?game=POCKET"
_NEXT_DATA_PATTERN = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)


def fetch_json(client: httpx.Client, url: str) -> dict[str, Any]:
    response = client.get(url, timeout=30.0)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {url}, got {type(payload)!r}")
    return payload


def fetch_text(client: httpx.Client, url: str) -> str:
    response = client.get(url, timeout=30.0)
    response.raise_for_status()
    return response.text


def parse_next_data_from_html(page_html: str) -> dict[str, Any] | None:
    match = _NEXT_DATA_PATTERN.search(page_html)
    if not match:
        return None

    raw_json = html.unescape(match.group(1)).strip()
    if not raw_json:
        return None

    parsed = json.loads(raw_json)
    if not isinstance(parsed, dict):
        return None
    return parsed


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    return html.unescape(text).strip()


def _to_int(value: str) -> int | None:
    raw = value.strip().replace(",", "")
    return int(raw) if raw.isdigit() else None


def _to_float(value: str) -> float | None:
    raw = value.strip()
    if raw in {"", "null", "NaN"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _selected_option_value(page_html: str, select_id: str, attr: str = "value") -> str | None:
    pattern_text = (
        rf'<select id="{re.escape(select_id)}">.*?<option[^>]*'
        rf'{re.escape(attr)}="([^"]+)"[^>]*selected'
    )
    pattern = re.compile(
        pattern_text,
        re.DOTALL,
    )
    match = pattern.search(page_html)
    return match.group(1) if match else None


def _selected_set_label(page_html: str) -> str | None:
    pattern = re.compile(
        r'<select id="set">.*?<option[^>]*selected[^>]*>(.*?)</option>',
        re.DOTALL,
    )
    match = pattern.search(page_html)
    if not match:
        return None
    return _strip_tags(match.group(1))


def parse_decks_table_from_html(page_html: str) -> dict[str, Any]:
    summary_match = re.search(
        r"<p>([\d,]+) tournaments,\s*([\d,]+) players,\s*([\d,]+) matches</p>",
        page_html,
    )

    overview = {
        "game": _selected_option_value(page_html, "game"),
        "format": _selected_option_value(page_html, "format"),
        "set_code": _selected_option_value(page_html, "set", attr="data-set"),
        "set_name": _selected_set_label(page_html),
        "tournaments": _to_int(summary_match.group(1)) if summary_match else None,
        "players": _to_int(summary_match.group(2)) if summary_match else None,
        "matches": _to_int(summary_match.group(3)) if summary_match else None,
    }

    decks: list[dict[str, Any]] = []
    for row_match in re.finditer(r"<tr([^>]*)>(.*?)</tr>", page_html, re.DOTALL):
        attrs = row_match.group(1)
        row_html = row_match.group(2)
        if 'data-share="' not in attrs:
            continue

        data_share = re.search(r'data-share="([^"]+)"', attrs)
        data_winrate = re.search(r'data-winrate="([^"]+)"', attrs)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if len(cells) < 7:
            continue

        deck_anchor = re.search(r'<a href="([^"]+)">(.*?)</a>', cells[2], re.DOTALL)
        score_anchor = re.search(r'<a href="([^"]+)">(.*?)</a>', cells[5], re.DOTALL)
        winrate_anchor = re.search(r'<a href="([^"]+)">(.*?)</a>', cells[6], re.DOTALL)

        icon_urls = re.findall(r'<img[^>]+class="pokemon"[^>]+src="([^"]+)"', cells[1], re.DOTALL)

        rank = _to_int(_strip_tags(cells[0]))
        count = _to_int(_strip_tags(cells[3]))
        share_text = _strip_tags(cells[4])
        share_pct = _to_float(share_text.replace("%", ""))
        match_record_text = _strip_tags(score_anchor.group(2)) if score_anchor else None
        if winrate_anchor:
            winrate_text = _strip_tags(winrate_anchor.group(2))
        else:
            winrate_text = _strip_tags(cells[6])
        winrate_pct = _to_float(winrate_text.replace("%", "")) if winrate_text else None

        deck_path = html.unescape(deck_anchor.group(1)) if deck_anchor else None
        deck_name = _strip_tags(deck_anchor.group(2)) if deck_anchor else None
        matchups_path = html.unescape(score_anchor.group(1)) if score_anchor else None
        slug = None
        if deck_path:
            slug_match = re.search(r"^/decks/([^?]+)", deck_path)
            slug = slug_match.group(1) if slug_match else None

        decks.append(
            {
                "rank": rank,
                "deck_name": deck_name,
                "slug": slug,
                "deck_url": urljoin(LIMITLESS_POCKET_DECKS_URL, deck_path) if deck_path else None,
                "matchups_url": urljoin(LIMITLESS_POCKET_DECKS_URL, matchups_path)
                if matchups_path
                else None,
                "count": count,
                "share_pct": share_pct,
                "share_ratio": _to_float(data_share.group(1)) if data_share else None,
                "win_rate_pct": winrate_pct,
                "win_rate_ratio": _to_float(data_winrate.group(1)) if data_winrate else None,
                "match_record": match_record_text,
                "icons": icon_urls,
                "is_hidden_by_default": 'class="more"' in attrs,
            }
        )

    return {"overview": overview, "decks": decks}


def extract_decklist_urls(archetype_html: str, limit: int = 3) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in re.finditer(
        r'href="(/tournament/[^"]+/player/[^"]+/decklist)"',
        archetype_html,
    ):
        href = urljoin(LIMITLESS_POCKET_DECKS_URL, html.unescape(match.group(1)))
        if href in seen:
            continue
        seen.add(href)
        urls.append(href)
        if len(urls) >= limit:
            break
    return urls


def parse_decklist_cards_from_html(decklist_html: str) -> list[dict[str, Any]]:
    hidden_input = re.search(
        r'<input type="hidden" name="input" value="([^"]+)"',
        decklist_html,
    )
    if not hidden_input:
        return []

    raw_json = html.unescape(hidden_input.group(1))
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    cards: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue

        set_code = str(item.get("set")) if item.get("set") else None
        number = str(item.get("number")) if item.get("number") else None
        card_id = f"{set_code}-{number}" if set_code and number else None

        card_url = None
        if set_code and number:
            card_url = f"https://pocket.limitlesstcg.com/cards/{set_code}/{number}"

        cards.append(
            {
                "count": _to_int(str(item.get("count", ""))),
                "name": str(item.get("name")) if item.get("name") else None,
                "set_code": set_code,
                "number": number,
                "card_id": card_id,
                "card_url": card_url,
            }
        )

    return cards
