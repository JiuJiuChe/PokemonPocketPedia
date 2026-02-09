"""Render non-LLM high-level meta overview report."""

from __future__ import annotations

import json
from datetime import date
from html import escape
from pathlib import Path
from typing import Any

from pokepocketpedia.storage.files import ensure_dir, write_text


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip().replace("%", "")
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def _normalize_image_url(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    url = raw.strip()
    if not url:
        return None
    lowered = url.lower()
    if lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return url
    if "assets.tcgdex.net" not in lowered:
        return url
    if lowered.endswith("/high") or lowered.endswith("/low"):
        return f"{url}.webp"
    return f"{url}/high.webp"


def _latest_snapshot_dir(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing metrics root: {path}")
    values: list[date] = []
    for child in path.iterdir():
        if not child.is_dir():
            continue
        try:
            values.append(date.fromisoformat(child.name))
        except ValueError:
            continue
    if not values:
        raise FileNotFoundError(f"No snapshot directories found under {path}")
    return max(values).isoformat()


def _win_rate_class(win_rate: float | None) -> tuple[str, str]:
    if win_rate is None:
        return ("win-neutral", "?")
    if win_rate >= 52.0:
        return ("win-hot", "🔥")
    if win_rate < 45.0:
        return ("win-cold", "❄️")
    return ("win-neutral", "•")


def _deck_count(deck: dict[str, Any]) -> int | None:
    raw = deck.get("count")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        cleaned = raw.strip().replace(",", "")
        if cleaned.isdigit():
            return int(cleaned)
    return None


def _weekly_title(snapshot: str) -> str:
    try:
        parsed = date.fromisoformat(snapshot)
        return f"Week {parsed.strftime('%m/%d/%Y')} Pokemon TCGP Meta Overview"
    except ValueError:
        return "Week Unknown Pokemon TCGP Meta Overview"


def render_meta_overview_report(
    processed_root: Path = Path("data/processed"),
    reports_root: Path = Path("data/processed/reports"),
    snapshot_date: str | None = None,
) -> Path:
    snapshot = snapshot_date or _latest_snapshot_dir(processed_root / "meta_metrics")

    top_decks = _read_json(processed_root / "meta_metrics" / snapshot / "top_decks.json")
    top_cards = _read_json(processed_root / "meta_metrics" / snapshot / "top_cards.json")
    deck_cards = _read_json(processed_root / "decks" / snapshot / "deck_cards.normalized.json")
    cards = _read_json(processed_root / "cards" / snapshot / "cards.normalized.json")

    deck_candidates = [item for item in top_decks.get("items", []) if isinstance(item, dict)]
    top_deck_items = sorted(
        deck_candidates,
        key=lambda item: (_deck_count(item) is None, -(_deck_count(item) or 0)),
    )[:10]
    top_card_items = [item for item in top_cards.get("items", []) if isinstance(item, dict)][:10]
    deck_card_items = [item for item in deck_cards.get("items", []) if isinstance(item, dict)]
    card_items = [item for item in cards.get("items", []) if isinstance(item, dict)]

    image_by_id: dict[str, str] = {}
    image_by_name: dict[str, str] = {}
    for item in card_items:
        card_id = str(item.get("card_id") or "").strip()
        card_name = str(item.get("name") or "").strip()
        image_url = _normalize_image_url(item.get("image"))
        if not image_url:
            continue
        if card_id:
            image_by_id[card_id.casefold()] = image_url
        if card_name:
            image_by_name[card_name.casefold()] = image_url

    def image_for_card(card_id: Any, card_name: Any) -> str | None:
        cid = str(card_id or "").strip().casefold()
        cname = str(card_name or "").strip().casefold()
        if cid and cid in image_by_id:
            return image_by_id[cid]
        if cname and cname in image_by_name:
            return image_by_name[cname]
        return None

    report_dir = reports_root / snapshot
    ensure_dir(report_dir)
    output_path = report_dir / "meta_overview.html"

    deck_rows: list[str] = []
    for deck in top_deck_items:
        slug = str(deck.get("slug") or "")
        deck_name = str(deck.get("deck_name") or slug or "Unknown deck")
        win_rate = _to_float(deck.get("win_rate_pct"))
        win_class, win_icon = _win_rate_class(win_rate)
        win_label = f"{win_rate:.2f}%" if win_rate is not None else "Unknown"
        deck_count = _deck_count(deck)
        count_label = f"{deck_count:,}" if deck_count is not None else "N/A"

        key_rows = [row for row in deck_card_items if str(row.get("deck_slug") or "") == slug]
        key_rows.sort(
            key=lambda row: (
                -float(row.get("avg_count") or 0.0),
                -float(row.get("presence_rate") or 0.0),
            )
        )
        key_cards_html: list[str] = []
        for row in key_rows[:6]:
            card_name = str(row.get("card_name") or "Unknown")
            image_url = image_for_card(row.get("card_id"), card_name)
            if image_url:
                key_cards_html.append(
                    f'<img src="{escape(image_url)}" alt="{escape(card_name)}" loading="lazy" />'
                )

        linked_name = escape(deck_name)
        deck_report_path = report_dir / f"recommendation.{slug}.html"
        if slug and deck_report_path.exists():
            linked_name = (
                f'<a href="{escape(deck_report_path.name)}" '
                f'class="deck-link">{escape(deck_name)}</a>'
            )

        key_cards_fragment = "".join(key_cards_html) or "<span>N/A</span>"
        deck_rows.append(
            "<tr>"
            f"<td>{linked_name}</td>"
            f'<td><div class="deck-keycards">{key_cards_fragment}</div></td>'
            f"<td>{escape(count_label)}</td>"
            f'<td><span class="{win_class}">{win_icon} {escape(win_label)}</span></td>'
            "</tr>"
        )

    card_cells: list[str] = []
    for card in top_card_items:
        card_name = str(card.get("card_name") or "Unknown")
        image_url = image_for_card(card.get("card_id"), card_name)
        pick_rate = _to_float(card.get("avg_presence_rate"))
        pick_label = f"{(pick_rate * 100):.1f}%" if pick_rate is not None else "N/A"
        meta_score = _to_float(card.get("weighted_share_points"))
        meta_score_label = f"{meta_score:.3f}" if meta_score is not None else "N/A"
        image_html = (
            f'<img src="{escape(image_url)}" alt="{escape(card_name)}" loading="lazy" />'
            if image_url
            else '<div class="card-placeholder">No Image</div>'
        )
        card_cells.append(
            '<article class="top-card">'
            f"{image_html}"
            f"<h4>{escape(card_name)}</h4>"
            f"<p>Pick rate: {escape(pick_label)}</p>"
            f"<p>Meta score: {escape(meta_score_label)}</p>"
            "</article>"
        )

    styles = "\n".join(
        [
            "    :root {",
            "      --bg: #f7f3e8;",
            "      --ink: #1f2a30;",
            "      --card: #ffffff;",
            "      --line: #ddd3bd;",
            "      --hot: #c62828;",
            "      --cold: #1e88e5;",
            "    }",
            "    body {",
            "      margin: 0;",
            "      font-family: 'Trebuchet MS', 'Gill Sans', sans-serif;",
            "      background: linear-gradient(180deg, #f7f3e8 0%, #efe7d6 100%);",
            "      color: var(--ink);",
            "    }",
            "    .wrap { max-width: 1200px; margin: 0 auto; padding: 2rem 1rem 3rem; }",
            "    .hero {",
            "      background: var(--card);",
            "      border: 1px solid var(--line);",
            "      border-radius: 16px;",
            "      padding: 1rem 1.2rem;",
            "      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);",
            "    }",
            "    h1 { margin: 0 0 .3rem 0; }",
            "    h2 {",
            "      margin: 1.6rem 0 .6rem 0;",
            "      padding-bottom: .35rem;",
            "      border-bottom: 2px solid var(--line);",
            "    }",
            "    table {",
            "      width: 100%;",
            "      border-collapse: collapse;",
            "      background: var(--card);",
            "      border: 1px solid var(--line);",
            "      border-radius: 12px;",
            "      overflow: hidden;",
            "    }",
            "    th, td {",
            "      padding: .65rem;",
            "      border-bottom: 1px solid #eee6d4;",
            "      vertical-align: middle;",
            "    }",
            "    th { text-align: left; background: #fbf7ef; }",
            "    .deck-link { color: #0f3c89; text-decoration: none; font-weight: 700; }",
            "    .deck-link:hover { text-decoration: underline; }",
            "    .deck-keycards { display: flex; gap: .35rem; flex-wrap: wrap; }",
            "    .deck-keycards img {",
            "      width: 44px;",
            "      height: 62px;",
            "      object-fit: cover;",
            "      border-radius: 6px;",
            "      border: 1px solid #eadfcf;",
            "    }",
            "    .win-hot { color: var(--hot); font-weight: 700; }",
            "    .win-cold { color: var(--cold); font-weight: 700; }",
            "    .win-neutral { color: #5d6970; font-weight: 700; }",
            "    .top-cards {",
            "      display: grid;",
            "      grid-template-columns: repeat(5, minmax(0, 1fr));",
            "      gap: .8rem;",
            "    }",
            "    .top-card {",
            "      background: var(--card);",
            "      border: 1px solid var(--line);",
            "      border-radius: 12px;",
            "      padding: .55rem;",
            "      text-align: center;",
            "    }",
            "    .top-card img {",
            "      width: 100%;",
            "      border-radius: 8px;",
            "      aspect-ratio: 2.5 / 3.5;",
            "      object-fit: cover;",
            "    }",
            "    .top-card h4 { font-size: .92rem; margin: .4rem 0 .2rem; }",
            "    .top-card p { margin: 0; font-size: .8rem; color: #4d5a61; }",
            "    .card-placeholder {",
            "      height: 150px;",
            "      display: grid;",
            "      place-items: center;",
            "      background: #f2ece0;",
            "      border-radius: 8px;",
            "      color: #886;",
            "    }",
            "    @media (max-width: 980px) {",
            "      .top-cards { grid-template-columns: repeat(3, minmax(0, 1fr)); }",
            "    }",
            "    @media (max-width: 760px) {",
            "      .top-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }",
            "    }",
        ]
    )

    title = _weekly_title(snapshot)
    html = (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{escape(title)}</title>\n"
        "  <style>\n"
        f"{styles}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <main class="wrap">\n'
        '    <section class="hero">\n'
        f"      <h1>{escape(title)}</h1>\n"
        "    </section>\n"
        "    <h2>Top 10 Popular Decks</h2>\n"
        "    <table>\n"
        "      <thead><tr><th>Deck</th><th>Key cards</th><th>Count</th>"
        "<th>Win rate</th></tr></thead>\n"
        f"      <tbody>{''.join(deck_rows)}</tbody>\n"
        "    </table>\n"
        "    <h2>Top 10 Popular Cards</h2>\n"
        f'    <section class="top-cards">{"".join(card_cells)}</section>\n'
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )

    write_text(output_path, html)
    return output_path
