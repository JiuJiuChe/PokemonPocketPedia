"""Phase 2 normalization pipeline."""

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


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.replace(",", "").strip()
        if raw.isdigit():
            return int(raw)
    return None


def _normalize_boosters(raw_boosters: Any) -> list[dict[str, str | None]]:
    if not isinstance(raw_boosters, list):
        return []

    normalized: list[dict[str, str | None]] = []
    for entry in raw_boosters:
        if isinstance(entry, dict):
            normalized.append(
                {
                    "id": str(entry.get("id")) if entry.get("id") else None,
                    "name": str(entry.get("name")) if entry.get("name") else None,
                }
            )
            continue
        if isinstance(entry, str):
            normalized.append({"id": entry, "name": None})
    return normalized


def _normalize_attacks(raw_attacks: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_attacks, list):
        return []

    normalized: list[dict[str, Any]] = []
    for attack in raw_attacks:
        if not isinstance(attack, dict):
            continue

        cost = attack.get("cost") if isinstance(attack.get("cost"), list) else []
        normalized.append(
            {
                "name": attack.get("name"),
                "cost": [str(item) for item in cost if isinstance(item, str)],
                "damage": attack.get("damage"),
                "effect": attack.get("effect"),
            }
        )
    return normalized


def _normalize_card(card: dict[str, Any], snapshot_date: str) -> dict[str, Any]:
    ability = card.get("ability") if isinstance(card.get("ability"), dict) else None
    set_data = card.get("set") if isinstance(card.get("set"), dict) else {}

    return {
        "snapshot_date": snapshot_date,
        "card_id": card.get("id"),
        "local_id": card.get("localId"),
        "name": card.get("name"),
        "category": card.get("category"),
        "trainer_type": card.get("trainerType"),
        "set_id": set_data.get("id"),
        "set_name": set_data.get("name"),
        "rarity": card.get("rarity"),
        "hp": _to_int(card.get("hp")),
        "types": [str(item) for item in card.get("types", []) if isinstance(item, str)],
        "stage": card.get("stage"),
        "ability_name": ability.get("name") if ability else None,
        "ability_text": ability.get("effect") if ability else None,
        "attacks": _normalize_attacks(card.get("attacks")),
        "effect": card.get("effect"),
        "boosters": _normalize_boosters(card.get("boosters")),
        "retreat": _to_int(card.get("retreat")),
        "updated": card.get("updated"),
        "image": card.get("image"),
    }


def _normalize_deck(
    deck: dict[str, Any],
    overview: dict[str, Any],
    snapshot_date: str,
) -> dict[str, Any]:
    return {
        "snapshot_date": snapshot_date,
        "rank": deck.get("rank"),
        "deck_name": deck.get("deck_name"),
        "slug": deck.get("slug"),
        "count": deck.get("count"),
        "share_pct": deck.get("share_pct"),
        "win_rate_pct": deck.get("win_rate_pct"),
        "match_record": deck.get("match_record"),
        "deck_url": deck.get("deck_url"),
        "matchups_url": deck.get("matchups_url"),
        "icons": deck.get("icons", []),
        "is_hidden_by_default": deck.get("is_hidden_by_default", False),
        "game": overview.get("game"),
        "format": overview.get("format"),
        "set_code": overview.get("set_code"),
        "set_name": overview.get("set_name"),
        "tournaments": overview.get("tournaments"),
        "players": overview.get("players"),
        "matches": overview.get("matches"),
    }


def _normalize_deck_cards(deck: dict[str, Any], snapshot_date: str) -> list[dict[str, Any]]:
    raw_cards = deck.get("sample_deck_cards", [])
    if not isinstance(raw_cards, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw_cards:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "snapshot_date": snapshot_date,
                "deck_slug": deck.get("slug"),
                "deck_name": deck.get("deck_name"),
                "deck_rank": deck.get("rank"),
                "deck_url": deck.get("deck_url"),
                "sample_decklist_url": deck.get("sample_decklist_url"),
                "sample_decklist_count": deck.get("sample_decklist_count"),
                "card_name": item.get("name"),
                "card_set_code": item.get("set_code"),
                "card_number": item.get("number"),
                "card_id": item.get("card_id"),
                "card_url": item.get("card_url"),
                "sample_count": item.get("sample_count"),
                "present_in_samples": item.get("present_in_samples"),
                "presence_rate": item.get("presence_rate"),
                "total_count": item.get("total_count"),
                "avg_count": item.get("avg_count"),
                # Backward-compatible single-count alias for downstream code.
                "count": (
                    item.get("count")
                    if item.get("count") is not None
                    else item.get("avg_count")
                ),
            }
        )
    return normalized


def _build_processed_dirs(processed_root: Path, snapshot_date: str) -> dict[str, Path]:
    return {
        "cards": processed_root / "cards" / snapshot_date,
        "decks": processed_root / "decks" / snapshot_date,
        "validation": processed_root / "validation" / snapshot_date,
    }


def run_normalize(
    raw_root: Path = Path("data/raw"),
    processed_root: Path = Path("data/processed"),
    snapshot_date: date | None = None,
) -> dict[str, Any]:
    date_value = _snapshot_date(snapshot_date)

    cards_raw_path = raw_root / "cards" / date_value / "cards.json"
    decks_raw_path = raw_root / "decks" / date_value / "decks.json"

    if not cards_raw_path.exists():
        raise FileNotFoundError(f"Missing cards raw snapshot: {cards_raw_path}")
    if not decks_raw_path.exists():
        raise FileNotFoundError(f"Missing decks raw snapshot: {decks_raw_path}")

    cards_raw = _read_json(cards_raw_path)
    decks_raw = _read_json(decks_raw_path)

    raw_cards = cards_raw.get("cards", [])
    raw_decks = decks_raw.get("decks", [])
    overview = decks_raw.get("overview", {})

    normalized_cards = [
        _normalize_card(item, date_value) for item in raw_cards if isinstance(item, dict)
    ]
    normalized_decks = [
        _normalize_deck(item, overview, date_value) for item in raw_decks if isinstance(item, dict)
    ]

    normalized_deck_cards: list[dict[str, Any]] = []
    for deck in raw_decks:
        if isinstance(deck, dict):
            normalized_deck_cards.extend(_normalize_deck_cards(deck, date_value))

    dirs = _build_processed_dirs(processed_root, date_value)
    for path in dirs.values():
        ensure_dir(path)

    cards_output_path = dirs["cards"] / "cards.normalized.json"
    decks_output_path = dirs["decks"] / "decks.normalized.json"
    deck_cards_output_path = dirs["decks"] / "deck_cards.normalized.json"
    validation_output_path = dirs["validation"] / "report.json"

    cards_payload = {
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "source_file": str(cards_raw_path),
        "items": normalized_cards,
        "stats": {"count": len(normalized_cards)},
    }
    decks_payload = {
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "source_file": str(decks_raw_path),
        "overview": overview,
        "items": normalized_decks,
        "stats": {"count": len(normalized_decks)},
    }
    deck_cards_payload = {
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "source_file": str(decks_raw_path),
        "items": normalized_deck_cards,
        "stats": {"count": len(normalized_deck_cards)},
    }

    write_json(cards_output_path, cards_payload)
    write_json(decks_output_path, decks_payload)
    write_json(deck_cards_output_path, deck_cards_payload)

    warnings: list[str] = []
    if not normalized_cards:
        warnings.append("No normalized cards were produced.")
    if not normalized_decks:
        warnings.append("No normalized decks were produced.")
    if not normalized_deck_cards:
        warnings.append("No deck card composition records were found in raw deck snapshots.")

    validation_payload = {
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "status": "ok" if not warnings else "ok_with_warnings",
        "checks": {
            "cards_raw_exists": cards_raw_path.exists(),
            "decks_raw_exists": decks_raw_path.exists(),
            "cards_normalized_count": len(normalized_cards),
            "decks_normalized_count": len(normalized_decks),
            "deck_cards_normalized_count": len(normalized_deck_cards),
        },
        "warnings": warnings,
        "outputs": {
            "cards": str(cards_output_path),
            "decks": str(decks_output_path),
            "deck_cards": str(deck_cards_output_path),
        },
    }
    write_json(validation_output_path, validation_payload)

    return {
        "snapshot_date": date_value,
        "status": validation_payload["status"],
        "outputs": validation_payload["outputs"],
        "counts": {
            "cards": len(normalized_cards),
            "decks": len(normalized_decks),
            "deck_cards": len(normalized_deck_cards),
        },
        "warnings": warnings,
        "validation_report": str(validation_output_path),
    }
