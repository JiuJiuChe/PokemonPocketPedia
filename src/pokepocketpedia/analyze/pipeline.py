"""Phase 3 analytics pipeline."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pokepocketpedia.storage.files import ensure_dir, write_json


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


def run_analyze(
    processed_root: Path = Path("data/processed"),
    snapshot_date: date | None = None,
) -> dict[str, Any]:
    date_value = _snapshot_date(snapshot_date)

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

    metrics_dir = processed_root / "meta_metrics" / date_value
    ensure_dir(metrics_dir)

    top_decks_path = metrics_dir / "top_decks.json"
    top_cards_path = metrics_dir / "top_cards.json"
    overview_path = metrics_dir / "overview.json"

    top_decks_payload = {
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "items": top_decks,
        "stats": {
            "count": len(top_decks),
            "top_10_count": min(10, len(top_decks)),
        },
    }

    top_cards_payload = {
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "items": top_cards,
        "stats": {
            "count": len(top_cards),
            "top_30_count": min(30, len(top_cards)),
        },
    }

    overview_payload = {
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

    write_json(top_decks_path, top_decks_payload)
    write_json(top_cards_path, top_cards_payload)
    write_json(overview_path, overview_payload)

    warnings: list[str] = []
    if not top_decks:
        warnings.append("No deck metrics were produced.")
    if not top_cards:
        warnings.append("No card metrics were produced.")

    return {
        "snapshot_date": date_value,
        "status": "ok" if not warnings else "ok_with_warnings",
        "counts": {
            "top_decks": len(top_decks),
            "top_cards": len(top_cards),
        },
        "outputs": {
            "top_decks": str(top_decks_path),
            "top_cards": str(top_cards_path),
            "overview": str(overview_path),
        },
        "warnings": warnings,
    }
