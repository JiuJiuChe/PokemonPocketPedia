"""Build LLM-ready recommendation context from processed artifacts."""

from __future__ import annotations

from typing import Any

from pokepocketpedia.api.data_access import read_artifact, resolve_snapshot_date
from pokepocketpedia.common.image_utils import normalize_image_url


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


def _tcgdex_image_fallback(card_id: Any) -> str | None:
    if not isinstance(card_id, str) or "-" not in card_id:
        return None
    parts = card_id.rsplit("-", 1)
    if len(parts) != 2:
        return None
    set_code, local_id = parts
    if not set_code or not local_id:
        return None
    return f"https://assets.tcgdex.net/en/tcgp/{set_code}/{local_id}/high.webp"


def _build_card_lookup(snapshot_date: str) -> dict[str, dict[str, Any]]:
    try:
        cards_payload = read_artifact("cards", snapshot_date, "cards.normalized.json")
    except FileNotFoundError:
        latest_cards_snapshot = resolve_snapshot_date("cards", None)
        cards_payload = read_artifact("cards", latest_cards_snapshot, "cards.normalized.json")

    items = [item for item in cards_payload.get("items", []) if isinstance(item, dict)]
    lookup: dict[str, dict[str, Any]] = {}
    for item in items:
        card_id = item.get("card_id")
        card_name = item.get("name")
        if card_id:
            lookup[f"id:{card_id}".casefold()] = item
        if card_name:
            lookup[f"name:{card_name}".casefold()] = item
    return lookup


def _card_from_lookup(
    row: dict[str, Any],
    lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    card_id = row.get("card_id")
    card_name = row.get("card_name")
    if card_id:
        found = lookup.get(f"id:{card_id}".casefold())
        if isinstance(found, dict):
            return found
    if card_name:
        found = lookup.get(f"name:{card_name}".casefold())
        if isinstance(found, dict):
            return found
    return None


def _card_meta(card: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(card, dict):
        return {"category": None, "trainer_type": None, "types": []}
    types = card.get("types")
    return {
        "category": card.get("category"),
        "trainer_type": card.get("trainer_type"),
        "types": [str(item) for item in types] if isinstance(types, list) else [],
    }


def _compatible_substitute(replace_meta: dict[str, Any], candidate_meta: dict[str, Any]) -> bool:
    replace_category = replace_meta.get("category")
    candidate_category = candidate_meta.get("category")
    if replace_category and candidate_category and replace_category != candidate_category:
        return False

    if replace_category == "Trainer":
        replace_trainer = replace_meta.get("trainer_type")
        candidate_trainer = candidate_meta.get("trainer_type")
        if replace_trainer and candidate_trainer and replace_trainer != candidate_trainer:
            return False
        return True

    if replace_category == "Pokemon":
        replace_types = set(replace_meta.get("types") or [])
        candidate_types = set(candidate_meta.get("types") or [])
        if replace_types and candidate_types:
            return bool(replace_types.intersection(candidate_types))
        return True

    return True


def _build_substitute_candidates(
    target_rows: list[dict[str, Any]],
    card_lookup: dict[str, dict[str, Any]],
    top_cards_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not top_cards_payload:
        return []

    top_cards = [item for item in top_cards_payload.get("items", []) if isinstance(item, dict)]
    if not top_cards:
        return []

    target_card_ids = {
        str(row.get("card_id"))
        for row in target_rows
        if row.get("card_id")
    }
    replace_pool = sorted(
        target_rows,
        key=lambda row: float(row.get("avg_count") or 0.0),
        reverse=True,
    )[:8]
    blocked_replace_keys = {
        "professor's research",
        "professors research",
        "pokeball",
        "poke ball",
    }

    candidates: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for replace_row in replace_pool:
        replace_card_id = str(replace_row.get("card_id") or "")
        replace_card_name = str(replace_row.get("card_name") or "")
        replace_key = replace_card_name.casefold().replace("é", "e").replace("-", " ")
        replace_key = " ".join(replace_key.split())
        if replace_key in blocked_replace_keys:
            continue
        replace_card = _card_from_lookup(replace_row, card_lookup)
        replace_meta = _card_meta(replace_card)

        per_replace: list[tuple[float, dict[str, Any]]] = []
        for item in top_cards:
            candidate_card_id = str(item.get("card_id") or "")
            candidate_card_name = str(item.get("card_name") or "")
            if not candidate_card_id or not candidate_card_name:
                continue
            if candidate_card_id in target_card_ids:
                continue
            if replace_card_id and candidate_card_id == replace_card_id:
                continue

            candidate_card = card_lookup.get(f"id:{candidate_card_id}".casefold())
            if candidate_card is None:
                candidate_card = card_lookup.get(f"name:{candidate_card_name}".casefold())
            candidate_meta = _card_meta(candidate_card)
            if not _compatible_substitute(replace_meta, candidate_meta):
                continue

            weighted = float(item.get("weighted_share_points") or 0.0)
            decks_seen = float(item.get("decks_seen") or 0.0)
            score = weighted + decks_seen * 0.01
            image = None
            if isinstance(candidate_card, dict):
                raw_image = candidate_card.get("image")
                if isinstance(raw_image, str) and raw_image:
                    image = raw_image
            per_replace.append(
                (
                    score,
                    {
                        "replace_card_id": replace_card_id or None,
                        "replace_card_name": replace_card_name or None,
                        "candidate_card_id": candidate_card_id,
                        "candidate_card_name": candidate_card_name,
                        "candidate_image_url": image,
                        "weighted_share_points": round(weighted, 6),
                        "decks_seen": int(decks_seen),
                        "compatibility_reason": (
                            f"category={candidate_meta.get('category')} "
                            f"trainer_type={candidate_meta.get('trainer_type')}"
                        ),
                    },
                )
            )

        per_replace.sort(key=lambda pair: pair[0], reverse=True)
        for _, candidate in per_replace[:3]:
            pair_key = (
                str(candidate.get("replace_card_id") or candidate.get("replace_card_name") or ""),
                str(candidate.get("candidate_card_id")),
            )
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            -float(item.get("weighted_share_points") or 0.0),
            -int(item.get("decks_seen") or 0),
        )
    )
    return candidates[:30]


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
    card_lookup = _build_card_lookup(resolved_snapshot)
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
    enriched_cards: list[dict[str, Any]] = []
    for row in deck_cards:
        card_id = row.get("card_id")
        card_name = row.get("card_name")
        lookup_item = None
        if card_id:
            lookup_item = card_lookup.get(f"id:{card_id}".casefold())
        if lookup_item is None and card_name:
            lookup_item = card_lookup.get(f"name:{card_name}".casefold())

        image_url = None
        if isinstance(lookup_item, dict):
            image_value = lookup_item.get("image")
            image_url = normalize_image_url(image_value)
        if image_url is None:
            image_url = _tcgdex_image_fallback(card_id)

        enriched_cards.append(
            {
                "card_id": card_id,
                "card_name": card_name,
                "avg_count": row.get("avg_count"),
                "presence_rate": row.get("presence_rate"),
                "sample_count": row.get("sample_count"),
                "card_url": row.get("card_url"),
                "image_url": image_url,
            }
        )

    key_cards = [row for row in enriched_cards[:key_card_limit]]

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
    substitute_candidates = _build_substitute_candidates(
        target_rows=deck_cards,
        card_lookup=card_lookup,
        top_cards_payload=top_cards_payload,
    )

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
        "deck_card_grid": enriched_cards[:20],
        "key_cards_from_archetype_metric": archetype_cards,
        "meta_context": {
            "top_meta_decks": top_meta_decks,
            "top_meta_cards": top_meta_cards,
            "overview": overview_payload if overview_payload else None,
        },
        "substitute_candidates": substitute_candidates,
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
            "substitute_cards",
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
