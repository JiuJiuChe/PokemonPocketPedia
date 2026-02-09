"""Render recommendation outputs into human-readable report files."""

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


def _key_card_fallback_lines(context_payload: dict[str, Any]) -> list[str]:
    key_cards = (
        context_payload.get("llm_input", {})
        .get("context", {})
        .get("key_cards_from_samples", [])
    )
    if not isinstance(key_cards, list):
        return []
    lines: list[str] = []
    for item in key_cards[:8]:
        if not isinstance(item, dict):
            continue
        card_name = item.get("card_name")
        if not card_name:
            continue
        avg_count = item.get("avg_count")
        presence_rate = item.get("presence_rate")
        lines.append(f"{card_name} (avg_count={avg_count}, presence_rate={presence_rate})")
    return lines


def render_recommendation_markdown(
    context_payload: dict[str, Any],
    llm_result: dict[str, Any],
) -> str:
    output = llm_result.get("structured_output", {})
    if not isinstance(output, dict):
        output = {}

    target = (
        context_payload.get("llm_input", {})
        .get("context", {})
        .get("target_deck", {})
    )
    if not isinstance(target, dict):
        target = {}

    lines: list[str] = []
    lines.append("# Deck Recommendation Report")
    lines.append("")
    lines.append(f"- Snapshot date: `{context_payload.get('snapshot_date')}`")
    lines.append(f"- Deck: `{context_payload.get('deck_slug')}`")
    lines.append(f"- Provider: `{llm_result.get('provider')}`")
    lines.append(f"- Model: `{llm_result.get('model')}`")
    lines.append(f"- Generated at: `{llm_result.get('generated_at')}`")
    usage = llm_result.get("usage", {})
    if isinstance(usage, dict):
        lines.append(f"- Input tokens: `{usage.get('input_tokens')}`")
        lines.append(f"- Output tokens: `{usage.get('output_tokens')}`")
    lines.append("")
    lines.append("## Deck Snapshot")
    lines.append("")
    lines.append(f"- Deck name: `{target.get('deck_name')}`")
    lines.append(f"- Share %: `{target.get('share_pct')}`")
    lines.append(f"- Win rate %: `{target.get('win_rate_pct')}`")
    lines.append(f"- Rank: `{target.get('rank')}`")
    lines.append("")
    lines.append("## Gameplan")
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
    lines.append("## Opening Plan")
    lines.append("")
    lines.append(
        _section_text(output.get("opening_plan"))
        or "Model did not provide opening-plan details."
    )
    lines.append("")
    lines.append("## Midgame Plan")
    lines.append("")
    lines.append(
        _section_text(output.get("midgame_plan"))
        or "Model did not provide midgame-plan details."
    )
    lines.append("")
    lines.append("## Closing Plan")
    lines.append("")
    lines.append(
        _section_text(output.get("closing_plan"))
        or "Model did not provide closing-plan details."
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
    lines.append("## Confidence and Limitations")
    lines.append("")
    lines.append(
        _section_text(output.get("confidence_and_limitations"))
        or "No confidence statement returned by model."
    )
    raw_text = _section_text(llm_result.get("raw_text"))
    if raw_text:
        lines.append("")
        lines.append("## Raw Model Response")
        lines.append("")
        lines.append(raw_text)
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_markdown_as_html(markdown_text: str, title: str = "Deck Recommendation Report") -> str:
    # Minimal markdown-to-html renderer for predictable CI output.
    html_lines: list[str] = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\">",
        f"  <title>{escape(title)}</title>",
        "  <style>",
        "    body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; "
        "max-width: 900px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }",
        "    code { background: #f2f2f2; padding: 0.1rem 0.3rem; border-radius: 4px; }",
        "    h1, h2 { line-height: 1.25; }",
        "  </style>",
        "</head>",
        "<body>",
    ]

    in_list = False
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<p></p>")
            continue
        if line.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{escape(line[2:])}</h1>")
            continue
        if line.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{escape(line[3:])}</h2>")
            continue
        if line.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{escape(line[2:])}</li>")
            continue
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(f"<p>{escape(line)}</p>")

    if in_list:
        html_lines.append("</ul>")
    html_lines.extend(["</body>", "</html>"])
    return "\n".join(html_lines) + "\n"
