"""Build LLM-ready recommendation context from processed artifacts."""

from __future__ import annotations

from typing import Any

from pokepocketpedia.api.data_access import read_artifact, resolve_snapshot_date


def _to_float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.replace("%", "").strip()
        try:
            return float(raw)
        except ValueError:
            return 0.0
    return 0.0


def _read_optional_meta(snapshot_date: str, filename: str) -> dict[str, Any] | None:
    try:
        return read_artifact("meta_metrics", snapshot_date, filename)
    except FileNotFoundError:
        return None


def build_recommendation_context(
    deck_slug: str,
    snapshot_date: str | None = None,
    key_card_limit: int = 12,
) -> dict[str, Any]:
    resolved_snapshot = resolve_snapshot_date("decks", snapshot_date)
    decks_payload = read_artifact("decks", resolved_snapshot, "decks.normalized.json")
    deck_cards_payload = read_artifact("decks", resolved_snapshot, "deck_cards.normalized.json")

    decks = [item for item in decks_payload.get("items", []) if isinstance(item, dict)]
    target = next(
        (item for item in decks if str(item.get("slug", "")).casefold() == deck_slug.casefold()),
        None,
    )
    if target is None:
        raise ValueError(f"Deck slug '{deck_slug}' not found in snapshot {resolved_snapshot}.")

    deck_rows = [item for item in deck_cards_payload.get("items", []) if isinstance(item, dict)]
    deck_cards = [
        row
        for row in deck_rows
        if str(row.get("deck_slug", "")).casefold() == str(target.get("slug", "")).casefold()
    ]
    deck_cards.sort(
        key=lambda row: (
            -_to_float(row.get("presence_rate")),
            -_to_float(row.get("avg_count")),
            str(row.get("card_name") or ""),
        )
    )
    key_cards = [
        {
            "card_id": row.get("card_id"),
            "card_name": row.get("card_name"),
            "avg_count": row.get("avg_count"),
            "presence_rate": row.get("presence_rate"),
            "sample_count": row.get("sample_count"),
            "card_url": row.get("card_url"),
        }
        for row in deck_cards[:key_card_limit]
    ]

    top_decks_payload = _read_optional_meta(resolved_snapshot, "top_decks.json")
    top_cards_payload = _read_optional_meta(resolved_snapshot, "top_cards.json")
    trends_payload = _read_optional_meta(resolved_snapshot, "trends_1d_7d.json")
    archetype_payload = _read_optional_meta(resolved_snapshot, "top_cards_by_archetype.json")
    overview_payload = _read_optional_meta(resolved_snapshot, "overview.json")

    top_decks = (
        [item for item in top_decks_payload.get("items", []) if isinstance(item, dict)]
        if top_decks_payload
        else []
    )
    top_cards = (
        [item for item in top_cards_payload.get("items", []) if isinstance(item, dict)]
        if top_cards_payload
        else []
    )
    deck_trend = None
    if trends_payload:
        deck_trend = next(
            (
                item
                for item in trends_payload.get("decks", [])
                if isinstance(item, dict)
                and str(item.get("deck_slug", "")).casefold()
                == str(target.get("slug", "")).casefold()
            ),
            None,
        )

    archetype_cards: list[dict[str, Any]] = []
    if archetype_payload:
        archetype = next(
            (
                item
                for item in archetype_payload.get("items", [])
                if isinstance(item, dict)
                and str(item.get("deck_slug", "")).casefold()
                == str(target.get("slug", "")).casefold()
            ),
            None,
        )
        if archetype and isinstance(archetype.get("top_cards"), list):
            archetype_cards = [
                item for item in archetype["top_cards"][:key_card_limit] if isinstance(item, dict)
            ]

    top_meta_decks = [
        {
            "deck_slug": item.get("slug"),
            "deck_name": item.get("deck_name"),
            "share_pct": item.get("share_pct"),
            "win_rate_pct": item.get("win_rate_pct"),
        }
        for item in top_decks[:5]
    ]
    top_meta_cards = [
        {
            "card_id": item.get("card_id"),
            "card_name": item.get("card_name"),
            "weighted_share_points": item.get("weighted_share_points"),
            "decks_seen": item.get("decks_seen"),
        }
        for item in top_cards[:10]
    ]

    context_bundle = {
        "snapshot_date": resolved_snapshot,
        "target_deck": {
            "deck_slug": target.get("slug"),
            "deck_name": target.get("deck_name"),
            "share_pct": target.get("share_pct"),
            "win_rate_pct": target.get("win_rate_pct"),
            "count": target.get("count"),
            "rank": target.get("rank"),
            "sample_decklist_count": target.get("sample_decklist_count"),
        },
        "trend_signals": {
            "delta_share_pct_1d": deck_trend.get("delta_share_pct_1d") if deck_trend else None,
            "delta_share_pct_7d": deck_trend.get("delta_share_pct_7d") if deck_trend else None,
            "reference_dates": (
                trends_payload.get("reference_dates")
                if trends_payload and isinstance(trends_payload.get("reference_dates"), dict)
                else None
            ),
        },
        "key_cards_from_samples": key_cards,
        "key_cards_from_archetype_metric": archetype_cards,
        "meta_context": {
            "top_meta_decks": top_meta_decks,
            "top_meta_cards": top_meta_cards,
            "overview": overview_payload if overview_payload else None,
        },
    }

    llm_input = {
        "task": (
            "Analyze how to play the target deck for ranked battles and provide actionable "
            "strategy guidance."
        ),
        "required_output_sections": [
            "deck_gameplan",
            "key_cards_and_roles",
            "opening_plan",
            "midgame_plan",
            "closing_plan",
            "tech_choices",
            "common_pitfalls",
            "confidence_and_limitations",
        ],
        "constraints": [
            "Use only provided context data.",
            "Do not invent card text not present in context.",
            "Call out uncertainty when evidence is missing.",
        ],
        "context": context_bundle,
    }

    return {
        "snapshot_date": resolved_snapshot,
        "deck_slug": target.get("slug"),
        "context_version": "1.0.0",
        "llm_input": llm_input,
    }

