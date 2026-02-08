"""Phase 3 analytics pipeline."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from pokepocketpedia.storage.files import ensure_dir, write_json
from pokepocketpedia.storage.schema_validation import validate_payload

SCHEMA_VERSION = "1.0.0"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _snapshot_date(value: date | None = None) -> str:
    return (value or date.today()).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _to_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip().replace("%", "")
        try:
            return float(raw)
        except ValueError:
            return default
    return default


def _top_decks_metrics(decks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_decks = sorted(
        decks,
        key=lambda item: (-_to_float(item.get("share_pct")), -_to_float(item.get("count"))),
    )
    return [
        {
            "rank": item.get("rank"),
            "deck_name": item.get("deck_name"),
            "slug": item.get("slug"),
            "share_pct": item.get("share_pct"),
            "count": item.get("count"),
            "win_rate_pct": item.get("win_rate_pct"),
            "match_record": item.get("match_record"),
            "deck_url": item.get("deck_url"),
        }
        for item in sorted_decks
    ]


def _top_cards_metrics(
    deck_cards: list[dict[str, Any]],
    deck_share_by_slug: dict[str, float],
) -> list[dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}

    for row in deck_cards:
        card_key = str(row.get("card_id") or row.get("card_name") or "")
        if not card_key:
            continue

        deck_slug = row.get("deck_slug")
        deck_share_pct = deck_share_by_slug.get(str(deck_slug), 0.0)
        avg_count = _to_float(
            row.get("avg_count"),
            default=_to_float(row.get("count"), default=0.0),
        )
        presence_rate = _to_float(row.get("presence_rate"), default=1.0)

        if card_key not in aggregated:
            aggregated[card_key] = {
                "card_id": row.get("card_id"),
                "card_name": row.get("card_name"),
                "card_set_code": row.get("card_set_code"),
                "card_number": row.get("card_number"),
                "card_url": row.get("card_url"),
                "decks_seen": set(),
                "weighted_share_points": 0.0,
                "total_avg_count": 0.0,
                "total_presence_rate": 0.0,
                "records": 0,
            }

        record = aggregated[card_key]
        record["decks_seen"].add(deck_slug)
        record["weighted_share_points"] += avg_count * (deck_share_pct / 100.0) * presence_rate
        record["total_avg_count"] += avg_count
        record["total_presence_rate"] += presence_rate
        record["records"] += 1

    result: list[dict[str, Any]] = []
    for value in aggregated.values():
        records = max(1, int(value["records"]))
        result.append(
            {
                "card_id": value["card_id"],
                "card_name": value["card_name"],
                "card_set_code": value["card_set_code"],
                "card_number": value["card_number"],
                "card_url": value["card_url"],
                "decks_seen": len(value["decks_seen"]),
                "weighted_share_points": round(value["weighted_share_points"], 6),
                "avg_count_across_decks": round(value["total_avg_count"] / records, 6),
                "avg_presence_rate": round(value["total_presence_rate"] / records, 6),
            }
        )

    result.sort(
        key=lambda item: (
            -_to_float(item.get("weighted_share_points")),
            -_to_float(item.get("decks_seen")),
            str(item.get("card_name") or ""),
        )
    )
    return result


def _top_cards_by_archetype(
    deck_cards: list[dict[str, Any]],
    decks_by_slug: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in deck_cards:
        deck_slug = row.get("deck_slug")
        if not deck_slug:
            continue
        grouped[str(deck_slug)].append(row)

    output: list[dict[str, Any]] = []
    for deck_slug, rows in grouped.items():
        deck_info = decks_by_slug.get(deck_slug, {})
        cards: list[dict[str, Any]] = []
        for row in rows:
            cards.append(
                {
                    "card_id": row.get("card_id"),
                    "card_name": row.get("card_name"),
                    "card_set_code": row.get("card_set_code"),
                    "card_number": row.get("card_number"),
                    "card_url": row.get("card_url"),
                    "avg_count": _to_float(
                        row.get("avg_count"),
                        default=_to_float(row.get("count")),
                    ),
                    "presence_rate": _to_float(row.get("presence_rate"), default=1.0),
                }
            )

        cards.sort(
            key=lambda item: (
                -_to_float(item.get("avg_count")),
                -_to_float(item.get("presence_rate")),
                str(item.get("card_name") or ""),
            )
        )

        output.append(
            {
                "deck_slug": deck_slug,
                "deck_name": deck_info.get("deck_name"),
                "share_pct": deck_info.get("share_pct"),
                "sample_deck_count": len(rows),
                "top_cards": cards[:30],
            }
        )

    output.sort(key=lambda item: -_to_float(item.get("share_pct")))
    return output


def _read_optional_metrics(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _read_json(path)


def _index_deck_shares(items: list[dict[str, Any]]) -> dict[str, float]:
    return {
        str(item.get("slug")): _to_float(item.get("share_pct"))
        for item in items
        if isinstance(item, dict) and item.get("slug")
    }


def _index_card_scores(items: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("card_id") or item.get("card_name") or "")
        if not key:
            continue
        out[key] = _to_float(item.get("weighted_share_points"))
    return out


def _find_previous_snapshot_path(metrics_root: Path, target_date: date) -> Path | None:
    if not metrics_root.exists():
        return None

    candidates: list[date] = []
    for child in metrics_root.iterdir():
        if not child.is_dir():
            continue
        try:
            snapshot = date.fromisoformat(child.name)
        except ValueError:
            continue
        if snapshot > target_date:
            continue
        if not (child / "top_decks.json").exists():
            continue
        if not (child / "top_cards.json").exists():
            continue
        candidates.append(snapshot)

    if not candidates:
        return None

    return metrics_root / max(candidates).isoformat()


def _trends_payload(
    snapshot_date: date,
    top_decks: list[dict[str, Any]],
    top_cards: list[dict[str, Any]],
    metrics_root: Path,
) -> dict[str, Any]:
    date_1d = snapshot_date - timedelta(days=1)
    date_7d = snapshot_date - timedelta(days=7)

    path_1d = _find_previous_snapshot_path(metrics_root, date_1d)
    path_7d = _find_previous_snapshot_path(metrics_root, date_7d)

    prev_decks_1d = []
    prev_cards_1d = []
    prev_decks_7d = []
    prev_cards_7d = []

    if path_1d:
        prev_decks_1d = _read_json(path_1d / "top_decks.json").get("items", [])
        prev_cards_1d = _read_json(path_1d / "top_cards.json").get("items", [])
    if path_7d:
        prev_decks_7d = _read_json(path_7d / "top_decks.json").get("items", [])
        prev_cards_7d = _read_json(path_7d / "top_cards.json").get("items", [])

    prev_deck_share_1d = _index_deck_shares(
        [item for item in prev_decks_1d if isinstance(item, dict)]
    )
    prev_deck_share_7d = _index_deck_shares(
        [item for item in prev_decks_7d if isinstance(item, dict)]
    )
    prev_card_score_1d = _index_card_scores(
        [item for item in prev_cards_1d if isinstance(item, dict)]
    )
    prev_card_score_7d = _index_card_scores(
        [item for item in prev_cards_7d if isinstance(item, dict)]
    )

    deck_trends: list[dict[str, Any]] = []
    for deck in top_decks:
        slug = str(deck.get("slug") or "")
        share = _to_float(deck.get("share_pct"))
        deck_trends.append(
            {
                "deck_slug": slug,
                "deck_name": deck.get("deck_name"),
                "share_pct": share,
                "delta_share_pct_1d": (
                    round(share - prev_deck_share_1d[slug], 6)
                    if slug in prev_deck_share_1d
                    else None
                ),
                "delta_share_pct_7d": (
                    round(share - prev_deck_share_7d[slug], 6)
                    if slug in prev_deck_share_7d
                    else None
                ),
            }
        )

    card_trends: list[dict[str, Any]] = []
    for card in top_cards:
        card_key = str(card.get("card_id") or card.get("card_name") or "")
        current_score = _to_float(card.get("weighted_share_points"))
        card_trends.append(
            {
                "card_id": card.get("card_id"),
                "card_name": card.get("card_name"),
                "weighted_share_points": current_score,
                "delta_weighted_share_1d": (
                    round(current_score - prev_card_score_1d[card_key], 6)
                    if card_key in prev_card_score_1d
                    else None
                ),
                "delta_weighted_share_7d": (
                    round(current_score - prev_card_score_7d[card_key], 6)
                    if card_key in prev_card_score_7d
                    else None
                ),
            }
        )

    return {
        "artifact_type": "meta_metrics.trends_1d_7d",
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": snapshot_date.isoformat(),
        "generated_at": _utc_now_iso(),
        "reference_dates": {
            "one_day": date_1d.isoformat(),
            "seven_day": date_7d.isoformat(),
            "one_day_available": path_1d is not None,
            "seven_day_available": path_7d is not None,
            "one_day_reference": path_1d.name if path_1d else None,
            "seven_day_reference": path_7d.name if path_7d else None,
        },
        "decks": deck_trends,
        "cards": card_trends,
        "stats": {
            "deck_count": len(deck_trends),
            "card_count": len(card_trends),
        },
    }


def run_analyze(
    processed_root: Path = Path("data/processed"),
    snapshot_date: date | None = None,
) -> dict[str, Any]:
    date_value = _snapshot_date(snapshot_date)
    current_date = date.fromisoformat(date_value)

    cards_path = processed_root / "cards" / date_value / "cards.normalized.json"
    decks_path = processed_root / "decks" / date_value / "decks.normalized.json"
    deck_cards_path = processed_root / "decks" / date_value / "deck_cards.normalized.json"

    for path in (cards_path, decks_path, deck_cards_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing processed input for analysis: {path}")

    cards_payload = _read_json(cards_path)
    decks_payload = _read_json(decks_path)
    deck_cards_payload = _read_json(deck_cards_path)

    cards_items = cards_payload.get("items", [])
    decks_items = decks_payload.get("items", [])
    deck_cards_items = deck_cards_payload.get("items", [])

    top_decks = _top_decks_metrics([item for item in decks_items if isinstance(item, dict)])
    deck_share_by_slug = {
        str(item.get("slug")): _to_float(item.get("share_pct"))
        for item in decks_items
        if isinstance(item, dict) and item.get("slug")
    }
    top_cards = _top_cards_metrics(
        [item for item in deck_cards_items if isinstance(item, dict)],
        deck_share_by_slug,
    )
    decks_by_slug = {
        str(item.get("slug")): item
        for item in decks_items
        if isinstance(item, dict) and item.get("slug")
    }
    top_cards_by_archetype = _top_cards_by_archetype(
        [item for item in deck_cards_items if isinstance(item, dict)],
        decks_by_slug,
    )

    metrics_dir = processed_root / "meta_metrics" / date_value
    metrics_root = processed_root / "meta_metrics"
    ensure_dir(metrics_dir)

    top_decks_path = metrics_dir / "top_decks.json"
    top_cards_path = metrics_dir / "top_cards.json"
    top_cards_by_archetype_path = metrics_dir / "top_cards_by_archetype.json"
    trends_path = metrics_dir / "trends_1d_7d.json"
    overview_path = metrics_dir / "overview.json"

    top_decks_payload = {
        "artifact_type": "meta_metrics.top_decks",
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "items": top_decks,
        "stats": {
            "count": len(top_decks),
            "top_10_count": min(10, len(top_decks)),
        },
    }

    top_cards_payload = {
        "artifact_type": "meta_metrics.top_cards",
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "items": top_cards,
        "stats": {
            "count": len(top_cards),
            "top_30_count": min(30, len(top_cards)),
        },
    }

    top_cards_by_archetype_payload = {
        "artifact_type": "meta_metrics.top_cards_by_archetype",
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "items": top_cards_by_archetype,
        "stats": {
            "count": len(top_cards_by_archetype),
        },
    }

    trends_payload = _trends_payload(
        snapshot_date=current_date,
        top_decks=top_decks,
        top_cards=top_cards,
        metrics_root=metrics_root,
    )

    overview_payload = {
        "artifact_type": "meta_metrics.overview",
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "inputs": {
            "cards_count": len(cards_items) if isinstance(cards_items, list) else 0,
            "decks_count": len(decks_items) if isinstance(decks_items, list) else 0,
            "deck_cards_count": len(deck_cards_items) if isinstance(deck_cards_items, list) else 0,
        },
        "highlights": {
            "most_popular_deck": top_decks[0] if top_decks else None,
            "most_popular_card": top_cards[0] if top_cards else None,
        },
    }

    validate_payload(top_decks_payload, "meta_metrics.top_decks")
    validate_payload(top_cards_payload, "meta_metrics.top_cards")
    validate_payload(top_cards_by_archetype_payload, "meta_metrics.top_cards_by_archetype")
    validate_payload(trends_payload, "meta_metrics.trends_1d_7d")
    validate_payload(overview_payload, "meta_metrics.overview")

    write_json(top_decks_path, top_decks_payload)
    write_json(top_cards_path, top_cards_payload)
    write_json(top_cards_by_archetype_path, top_cards_by_archetype_payload)
    write_json(trends_path, trends_payload)
    write_json(overview_path, overview_payload)

    warnings: list[str] = []
    if not top_decks:
        warnings.append("No deck metrics were produced.")
    if not top_cards:
        warnings.append("No card metrics were produced.")
    if not top_cards_by_archetype:
        warnings.append("No archetype card metrics were produced.")
    if not trends_payload["reference_dates"]["one_day_available"]:
        warnings.append("No prior metrics snapshot available for 1-day trend reference.")
    if not trends_payload["reference_dates"]["seven_day_available"]:
        warnings.append("No prior metrics snapshot available for 7-day trend reference.")

    return {
        "snapshot_date": date_value,
        "status": "ok" if not warnings else "ok_with_warnings",
        "counts": {
            "top_decks": len(top_decks),
            "top_cards": len(top_cards),
            "top_cards_by_archetype": len(top_cards_by_archetype),
        },
        "outputs": {
            "top_decks": str(top_decks_path),
            "top_cards": str(top_cards_path),
            "top_cards_by_archetype": str(top_cards_by_archetype_path),
            "trends_1d_7d": str(trends_path),
            "overview": str(overview_path),
        },
        "warnings": warnings,
    }
