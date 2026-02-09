"""Render recommendation outputs into human-readable report files."""
# ruff: noqa: E501

from __future__ import annotations

from html import escape
from typing import Any


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _section_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _is_fallback_confidence(text: str) -> bool:
    lowered = text.casefold()
    return "fallback strategy generated because structured model response was unavailable" in lowered


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


def _card_count(value: Any) -> int:
    parsed = _to_float(value)
    if parsed is None:
        return 1
    rounded = int(round(parsed))
    return rounded if rounded > 0 else 1


def _context_cards(context_payload: dict[str, Any]) -> list[dict[str, Any]]:
    context = context_payload.get("llm_input", {}).get("context", {})
    if not isinstance(context, dict):
        return []
    deck_grid = context.get("deck_card_grid")
    if isinstance(deck_grid, list):
        return [item for item in deck_grid if isinstance(item, dict)]
    key_cards = context.get("key_cards_from_samples")
    if isinstance(key_cards, list):
        return [item for item in key_cards if isinstance(item, dict)]
    return []


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


def _key_card_fallback_lines(context_payload: dict[str, Any]) -> list[str]:
    cards = _context_cards(context_payload)
    lines: list[str] = []
    for item in cards[:8]:
        card_name = item.get("card_name")
        if not card_name:
            continue
        avg_count = item.get("avg_count")
        presence_rate = item.get("presence_rate")
        lines.append(f"{card_name} (avg_count={avg_count}, presence_rate={presence_rate})")
    return lines


def _parse_key_card_roles(
    role_entries: list[Any],
    cards: list[dict[str, Any]],
) -> list[dict[str, str | None]]:
    cards_by_name = {
        str(item.get("card_name", "")).casefold(): item for item in cards if item.get("card_name")
    }
    known_names = [str(item.get("card_name", "")) for item in cards if item.get("card_name")]
    parsed: list[dict[str, str | None]] = []
    for entry in role_entries:
        text = str(entry).strip()
        if not text:
            continue
        if ":" in text:
            card_name, role = text.split(":", 1)
            card_name = card_name.strip()
            role = role.strip()
        else:
            card_name = text
            role = "Key role not explicitly provided."

        # Normalize entries like "Rare Candy (A3-144)".
        if " (" in card_name and card_name.endswith(")"):
            card_name = card_name.split(" (", 1)[0].strip()

        card = cards_by_name.get(card_name.casefold())
        if card is None:
            lowered = text.casefold()
            best_known: str | None = None
            best_pos: int | None = None
            for known in known_names:
                pos = lowered.find(known.casefold())
                if pos == -1:
                    continue
                if best_pos is None or pos < best_pos or (pos == best_pos and len(known) > len(best_known or "")):
                    best_known = known
                    best_pos = pos
            if best_known is not None:
                card_name = best_known
                card = cards_by_name.get(best_known.casefold())

        image_url = _normalize_image_url(card.get("image_url")) if isinstance(card, dict) else None
        parsed.append(
            {
                "card_name": card_name,
                "role": role,
                "image_url": image_url,
            }
        )
    return parsed


def _markdown_card_grid(
    cards: list[dict[str, Any]], columns: int = 5, max_cards: int = 20
) -> list[str]:
    selected = cards[:max_cards]
    if not selected:
        return ["No card image data available for this deck snapshot."]

    lines: list[str] = []
    header = "|" + "|".join([f" Card {i + 1} " for i in range(columns)]) + "|"
    divider = "|" + "|".join([" --- " for _ in range(columns)]) + "|"
    lines.append(header)
    lines.append(divider)

    rows = [selected[i : i + columns] for i in range(0, len(selected), columns)]
    for row in rows:
        cells: list[str] = []
        for item in row:
            name = str(item.get("card_name") or "Unknown")
            image_url = item.get("image_url")
            image_url = _normalize_image_url(image_url)
            count_label = f"x{_card_count(item.get('avg_count'))}"
            if isinstance(image_url, str) and image_url:
                cell = f"![{name}]({image_url})<br>{name} ({count_label})"
            else:
                cell = f"{name} ({count_label})"
            cells.append(cell)
        while len(cells) < columns:
            cells.append(" ")
        lines.append("|" + "|".join(cells) + "|")
    return lines


def render_recommendation_markdown(
    context_payload: dict[str, Any],
    llm_result: dict[str, Any],
) -> str:
    output = llm_result.get("structured_output", {})
    if not isinstance(output, dict):
        output = {}

    target = context_payload.get("llm_input", {}).get("context", {}).get("target_deck", {})
    if not isinstance(target, dict):
        target = {}

    lines: list[str] = []
    lines.append("# Deck Recommendation Report")
    lines.append("")
    lines.append(f"- Snapshot date: `{context_payload.get('snapshot_date')}`")
    lines.append(f"- Deck slug: `{context_payload.get('deck_slug')}`")
    lines.append(f"- Deck name: `{target.get('deck_name')}`")
    lines.append(f"- Meta share: `{target.get('share_pct')}`")
    lines.append(f"- Win rate: `{target.get('win_rate_pct')}`")
    lines.append(f"- Meta rank: `{target.get('rank')}`")
    lines.append(f"- Provider: `{llm_result.get('provider')}`")
    lines.append(f"- Model: `{llm_result.get('model')}`")
    lines.append(f"- Generated at: `{llm_result.get('generated_at')}`")
    usage = llm_result.get("usage", {})
    if isinstance(usage, dict):
        lines.append(f"- Input tokens: `{usage.get('input_tokens')}`")
        lines.append(f"- Output tokens: `{usage.get('output_tokens')}`")
    lines.append("")
    lines.append("## Deck Cards")
    lines.append("")
    lines.extend(_markdown_card_grid(_context_cards(context_payload), columns=5, max_cards=20))
    lines.append("")
    lines.append("## Game Plan")
    lines.append("")
    lines.append(
        _section_text(output.get("deck_gameplan"))
        or "Model did not provide a full gameplan section."
    )
    lines.append("")
    lines.append("## Key Cards and Roles")
    lines.append("")
    key_roles = _as_list(output.get("key_cards_and_roles"))
    if not key_roles:
        key_roles = _key_card_fallback_lines(context_payload)
    for item in key_roles:
        lines.append(f"- {item}")
    if not key_roles:
        lines.append("- No key-card role details returned by model.")
    lines.append("")
    lines.append("### Open -> Mid -> Close")
    lines.append("")
    lines.append(
        f"- Open: {_section_text(output.get('opening_plan')) or 'Model did not provide opening-plan details.'}"
    )
    lines.append(
        f"- Mid: {_section_text(output.get('midgame_plan')) or 'Model did not provide midgame-plan details.'}"
    )
    lines.append(
        f"- Close: {_section_text(output.get('closing_plan')) or 'Model did not provide closing-plan details.'}"
    )
    lines.append("")
    lines.append("## Tech Choices")
    lines.append("")
    tech_choices = _as_list(output.get("tech_choices"))
    for item in tech_choices:
        lines.append(f"- {item}")
    if not tech_choices:
        lines.append("- No specific tech swaps suggested in this run.")
    lines.append("")
    lines.append("## Common Pitfalls")
    lines.append("")
    pitfalls = _as_list(output.get("common_pitfalls"))
    for item in pitfalls:
        lines.append(f"- {item}")
    if not pitfalls:
        lines.append("- No explicit pitfalls were listed in this run.")
    lines.append("")
    confidence_text = _section_text(output.get("confidence_and_limitations"))
    if not _is_fallback_confidence(confidence_text):
        lines.append("## Confidence and Limitations")
        lines.append("")
        lines.append(confidence_text or "No confidence statement returned by model.")
    raw_text = _section_text(llm_result.get("raw_text"))
    if raw_text:
        lines.append("")
        lines.append("## Raw Model Response")
        lines.append("")
        lines.append(raw_text)
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_recommendation_html(
    context_payload: dict[str, Any],
    llm_result: dict[str, Any],
) -> str:
    output = llm_result.get("structured_output", {})
    if not isinstance(output, dict):
        output = {}
    context = context_payload.get("llm_input", {}).get("context", {})
    if not isinstance(context, dict):
        context = {}
    target = context.get("target_deck", {}) if isinstance(context.get("target_deck"), dict) else {}
    cards = _context_cards(context_payload)[:20]
    win_rate_value = _to_float(target.get("win_rate_pct"))

    def section_text(key: str, fallback: str) -> str:
        return escape(_section_text(output.get(key)) or fallback)

    def list_items(values: list[Any], fallback: str) -> str:
        items = [escape(str(item)) for item in values if str(item).strip()]
        if not items:
            return f"<li>{escape(fallback)}</li>"
        return "".join(f"<li>{item}</li>" for item in items)

    card_cells: list[str] = []
    for card in cards:
        name = escape(str(card.get("card_name") or "Unknown"))
        image_url = card.get("image_url")
        image_url = _normalize_image_url(image_url)
        avg_count = escape(str(card.get("avg_count")))
        presence = escape(str(card.get("presence_rate")))
        count_label = f"x{_card_count(card.get('avg_count'))}"
        image_html = (
            f'<img src="{escape(str(image_url))}" alt="{name}" loading="lazy" />'
            if isinstance(image_url, str) and image_url
            else '<div class="placeholder">No Image</div>'
        )
        card_cells.append(
            '<article class="card-tile">'
            f'<span class="count-badge">{escape(count_label)}</span>'
            f"{image_html}"
            f"<h4>{name}</h4>"
            f"<p>avg_count={avg_count} | presence={presence}</p>"
            "</article>"
        )
    if not card_cells:
        card_cells.append("<p>No card image data available for this deck snapshot.</p>")

    if win_rate_value is None:
        win_rate_label = "Unknown"
        win_rate_class = "win-neutral"
        win_rate_icon = "?"
    elif win_rate_value >= 52.0:
        win_rate_label = f"{win_rate_value:.2f}%"
        win_rate_class = "win-hot"
        win_rate_icon = "🔥"
    elif win_rate_value < 45.0:
        win_rate_label = f"{win_rate_value:.2f}%"
        win_rate_class = "win-cold"
        win_rate_icon = "❄️"
    else:
        win_rate_label = f"{win_rate_value:.2f}%"
        win_rate_class = "win-neutral"
        win_rate_icon = "•"

    generated_raw = str(llm_result.get("generated_at") or "")
    report_date = generated_raw.split("T", 1)[0] if "T" in generated_raw else generated_raw
    if not report_date:
        report_date = str(context_payload.get("snapshot_date") or "")
    report_date = escape(report_date)
    deck_name = escape(str(target.get("deck_name") or context_payload.get("deck_slug")))

    key_roles_raw = _as_list(output.get("key_cards_and_roles"))
    parsed_roles = _parse_key_card_roles(key_roles_raw, cards)
    if not parsed_roles:
        for fallback in _key_card_fallback_lines(context_payload)[:6]:
            if " (" in fallback:
                fallback_name = fallback.split(" (", 1)[0]
            else:
                fallback_name = fallback
            image_url = None
            for card in cards:
                if str(card.get("card_name", "")).casefold() == fallback_name.casefold():
                    image_url = _normalize_image_url(card.get("image_url"))
                    break
            parsed_roles.append(
                {
                    "card_name": fallback_name,
                    "role": "Core piece in sampled lists.",
                    "image_url": image_url,
                }
            )

    role_cells: list[str] = []
    for role in parsed_roles[:8]:
        name = escape(str(role.get("card_name") or "Unknown"))
        role_text = escape(str(role.get("role") or ""))
        image_url = _normalize_image_url(role.get("image_url"))
        thumb = (
            f'<img src="{escape(str(image_url))}" alt="{name}" loading="lazy" />'
            if isinstance(image_url, str) and image_url
            else '<div class="role-thumb-placeholder">No Image</div>'
        )
        role_cells.append(
            '<article class="role-row">'
            f'<div class="role-thumb">{thumb}</div>'
            f'<div class="role-text"><h4>{name}</h4><p>{role_text}</p></div>'
            "</article>"
        )
    if not role_cells:
        role_cells.append("<p>No key-card role details returned by model.</p>")

    stage_names = ["Open", "Mid", "Close"]
    stage_keys = ["opening_plan", "midgame_plan", "closing_plan"]
    stage_fallbacks = [
        "Model did not provide opening-plan details.",
        "Model did not provide midgame-plan details.",
        "Model did not provide closing-plan details.",
    ]
    stage_cells: list[str] = []
    for idx in range(3):
        card = cards[idx] if idx < len(cards) else {}
        card_name = escape(str(card.get("card_name") or "No card"))
        desc = section_text(stage_keys[idx], stage_fallbacks[idx])
        stage_cells.append(
            '<article class="stage-card">'
            f'<h3>{stage_names[idx]}</h3>'
            f'<h4>{card_name}</h4>'
            f'<p>{desc}</p>'
            "</article>"
        )

    confidence_text = _section_text(output.get("confidence_and_limitations"))
    confidence_section = ""
    if not _is_fallback_confidence(confidence_text):
        confidence_section = (
            "    <h2>Confidence and Limitations</h2>\n"
            f'    <section class="panel"><p>{section_text("confidence_and_limitations", "No confidence statement returned by model.")}</p></section>\n'
        )

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{deck_name} - Strategy Report</title>\n"
        "  <style>\n"
        "    :root { --bg: #f7f3e8; --ink: #1f2a30; --accent: #d94841; --card: #ffffff; --line: #ddd3bd; --hot: #c62828; --cold: #1e88e5; }\n"
        "    body { margin: 0; font-family: 'Trebuchet MS', 'Gill Sans', sans-serif; background: linear-gradient(180deg, #f7f3e8 0%, #efe7d6 100%); color: var(--ink); }\n"
        "    .wrap { max-width: 1100px; margin: 0 auto; padding: 2rem 1rem 3rem; }\n"
        "    .hero { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 1rem 1.2rem; box-shadow: 0 4px 14px rgba(0,0,0,0.06); }\n"
        "    h1 { margin: 0 0 .5rem 0; font-size: 2rem; }\n"
        "    h2 { margin: 1.6rem 0 .6rem 0; padding-bottom: .35rem; border-bottom: 2px solid var(--line); }\n"
        "    .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: .6rem; }\n"
        "    .chip { background: #fff7ef; border: 1px solid #e8dac6; border-left: 5px solid var(--accent); padding: .5rem .6rem; border-radius: 10px; }\n"
        "    .grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .8rem; }\n"
        "    .card-tile { position: relative; background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: .45rem; text-align: center; }\n"
        "    .count-badge { position: absolute; top: .4rem; right: .4rem; background: #0f172a; color: #fff; border-radius: 999px; padding: .1rem .45rem; font-size: .72rem; font-weight: 700; }\n"
        "    .card-tile img { width: 100%; border-radius: 8px; aspect-ratio: 2.5 / 3.5; object-fit: cover; }\n"
        "    .placeholder { height: 160px; display: grid; place-items: center; background: #f2ece0; border-radius: 8px; color: #836; }\n"
        "    .card-tile h4 { font-size: .9rem; margin: .4rem 0 .2rem; }\n"
        "    .card-tile p { margin: 0; font-size: .76rem; color: #5d6970; }\n"
        "    .panel { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: .8rem 1rem; margin: .6rem 0; }\n"
        "    .win-hot { color: var(--hot); font-weight: 700; }\n"
        "    .win-cold { color: var(--cold); font-weight: 700; }\n"
        "    .win-neutral { color: #5d6970; font-weight: 700; }\n"
        "    .role-grid { display: grid; grid-template-columns: 1fr; gap: .6rem; }\n"
        "    .role-row { display: grid; grid-template-columns: 80px 1fr; gap: .8rem; align-items: center; background: #fffaf2; border: 1px solid #eadfcf; border-radius: 10px; padding: .45rem; }\n"
        "    .role-thumb img { width: 72px; height: 100px; object-fit: cover; border-radius: 8px; }\n"
        "    .role-thumb-placeholder { width: 72px; height: 100px; display: grid; place-items: center; border-radius: 8px; background: #f2ece0; font-size: .72rem; }\n"
        "    .role-text h4 { margin: 0 0 .2rem 0; font-size: .95rem; }\n"
        "    .role-text p { margin: 0; font-size: .88rem; }\n"
        "    .stage-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .8rem; }\n"
        "    .stage-card { background: #fffaf2; border: 1px solid #eadfcf; border-radius: 12px; padding: .65rem; }\n"
        "    .stage-card h3 { margin: 0 0 .4rem 0; font-size: 1rem; }\n"
        "    .stage-card h4 { margin: .45rem 0 .3rem 0; font-size: .9rem; }\n"
        "    .stage-card p { margin: 0; font-size: .88rem; }\n"
        "    ul { margin: .2rem 0 .2rem 1.2rem; }\n"
        "    @media (max-width: 980px) { .grid { grid-template-columns: repeat(4, minmax(0, 1fr)); } }\n"
        "    @media (max-width: 760px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .stage-grid { grid-template-columns: 1fr; } h1 { font-size: 1.5rem; } }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <main class="wrap">\n'
        '    <section class="hero">\n'
        f"      <h1>{deck_name} Strategy Report</h1>\n"
        '      <div class="meta">'
        f'        <div class="chip"><strong>📅 Report time</strong><br>{report_date}</div>'
        f'        <div class="chip"><strong>Win Rate</strong><br><span class="{win_rate_class}">{win_rate_icon} {win_rate_label}</span></div>'
        "      </div>\n"
        "    </section>\n"
        "    <h2>Deck Cards (5 x 4)</h2>\n"
        f'    <section class="grid">{"".join(card_cells)}</section>\n'
        "    <h2>Game Plan</h2>\n"
        f'    <section class="panel"><p>{section_text("deck_gameplan", "Model did not provide a full gameplan section.")}</p></section>\n'
        "    <h2>Key Cards and Roles</h2>\n"
        f'    <section class="role-grid">{"".join(role_cells)}</section>\n'
        "    <h2>Game Plan Stages</h2>\n"
        f'    <section class="stage-grid">{"".join(stage_cells)}</section>\n'
        "    <h2>Tech Choices</h2>\n"
        f'    <section class="panel"><ul>{list_items(_as_list(output.get("tech_choices")), "No specific tech swaps suggested in this run.")}</ul></section>\n'
        "    <h2>Common Pitfalls</h2>\n"
        f'    <section class="panel"><ul>{list_items(_as_list(output.get("common_pitfalls")), "No explicit pitfalls were listed in this run.")}</ul></section>\n'
        f"{confidence_section}"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )
