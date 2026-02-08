"""Phase 2 normalization pipeline."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
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


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.replace("%", "").strip()
        try:
            return float(raw)
        except ValueError:
            return None
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
        "count": _to_int(deck.get("count")),
        "share_pct": _to_float(deck.get("share_pct")),
        "win_rate_pct": _to_float(deck.get("win_rate_pct")),
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
                "presence_rate": _to_float(item.get("presence_rate")),
                "total_count": _to_float(item.get("total_count")),
                "avg_count": _to_float(item.get("avg_count")),
                "count": (
                    item.get("count")
                    if item.get("count") is not None
                    else _to_float(item.get("avg_count"))
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


def _validation_issue(
    severity: str,
    code: str,
    message: str,
    count: int | None = None,
) -> dict[str, Any]:
    issue: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if count is not None:
        issue["count"] = count
    return issue


def _top_level_contract_issues(
    cards_payload: dict[str, Any],
    decks_payload: dict[str, Any],
    deck_cards_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    required = {
        "cards.normalized": [
            "artifact_type",
            "schema_version",
            "snapshot_date",
            "generated_at",
            "source_file",
            "items",
            "stats",
        ],
        "decks.normalized": [
            "artifact_type",
            "schema_version",
            "snapshot_date",
            "generated_at",
            "source_file",
            "overview",
            "items",
            "stats",
        ],
        "deck_cards.normalized": [
            "artifact_type",
            "schema_version",
            "snapshot_date",
            "generated_at",
            "source_file",
            "items",
            "stats",
        ],
    }
    payloads = {
        "cards.normalized": cards_payload,
        "decks.normalized": decks_payload,
        "deck_cards.normalized": deck_cards_payload,
    }
    for artifact_type, fields in required.items():
        payload = payloads[artifact_type]
        missing = [field for field in fields if field not in payload]
        if missing:
            issues.append(
                _validation_issue(
                    "error",
                    "contract.missing_top_level_fields",
                    f"{artifact_type} missing fields: {', '.join(missing)}",
                    len(missing),
                )
            )
    return issues


def _content_validation_issues(
    normalized_cards: list[dict[str, Any]],
    normalized_decks: list[dict[str, Any]],
    normalized_deck_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    if not normalized_cards:
        issues.append(
            _validation_issue(
                "warning",
                "cards.empty",
                "No normalized cards were produced.",
            )
        )
    if not normalized_decks:
        issues.append(
            _validation_issue(
                "warning",
                "decks.empty",
                "No normalized decks were produced.",
            )
        )
    if not normalized_deck_cards:
        issues.append(
            _validation_issue(
                "warning",
                "deck_cards.empty",
                "No deck card composition records were found in raw deck snapshots.",
            )
        )

    missing_card_ids = sum(1 for card in normalized_cards if not card.get("card_id"))
    missing_card_names = sum(1 for card in normalized_cards if not card.get("name"))
    if missing_card_ids:
        issues.append(
            _validation_issue(
                "error",
                "cards.missing_card_id",
                "Some normalized cards are missing card_id.",
                missing_card_ids,
            )
        )
    if missing_card_names:
        issues.append(
            _validation_issue(
                "error",
                "cards.missing_name",
                "Some normalized cards are missing name.",
                missing_card_names,
            )
        )

    card_id_counts = Counter(
        card.get("card_id") for card in normalized_cards if card.get("card_id")
    )
    duplicate_card_ids = sum(1 for _, count in card_id_counts.items() if count > 1)
    if duplicate_card_ids:
        issues.append(
            _validation_issue(
                "warning",
                "cards.duplicate_card_id",
                "Duplicate card_id values found in normalized cards.",
                duplicate_card_ids,
            )
        )

    missing_deck_slug = sum(1 for deck in normalized_decks if not deck.get("slug"))
    missing_deck_name = sum(1 for deck in normalized_decks if not deck.get("deck_name"))
    missing_deck_share = sum(1 for deck in normalized_decks if deck.get("share_pct") is None)
    if missing_deck_slug:
        issues.append(
            _validation_issue(
                "error",
                "decks.missing_slug",
                "Some normalized decks are missing slug.",
                missing_deck_slug,
            )
        )
    if missing_deck_name:
        issues.append(
            _validation_issue(
                "error",
                "decks.missing_name",
                "Some normalized decks are missing deck_name.",
                missing_deck_name,
            )
        )
    if missing_deck_share:
        issues.append(
            _validation_issue(
                "warning",
                "decks.missing_share_pct",
                "Some normalized decks are missing share_pct.",
                missing_deck_share,
            )
        )

    deck_slug_counts = Counter(deck.get("slug") for deck in normalized_decks if deck.get("slug"))
    duplicate_deck_slugs = sum(1 for _, count in deck_slug_counts.items() if count > 1)
    if duplicate_deck_slugs:
        issues.append(
            _validation_issue(
                "warning",
                "decks.duplicate_slug",
                "Duplicate slug values found in normalized decks.",
                duplicate_deck_slugs,
            )
        )

    missing_deck_card_slug = sum(1 for row in normalized_deck_cards if not row.get("deck_slug"))
    missing_deck_card_identity = sum(
        1
        for row in normalized_deck_cards
        if not row.get("card_id") and not row.get("card_name")
    )
    if missing_deck_card_slug:
        issues.append(
            _validation_issue(
                "warning",
                "deck_cards.missing_deck_slug",
                "Some normalized deck-card rows are missing deck_slug.",
                missing_deck_card_slug,
            )
        )
    if missing_deck_card_identity:
        issues.append(
            _validation_issue(
                "warning",
                "deck_cards.missing_card_identity",
                "Some normalized deck-card rows are missing both card_id and card_name.",
                missing_deck_card_identity,
            )
        )

    return issues


def _validation_status(issues: list[dict[str, Any]]) -> str:
    if any(issue.get("severity") == "error" for issue in issues):
        return "error"
    if any(issue.get("severity") == "warning" for issue in issues):
        return "ok_with_warnings"
    return "ok"


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
        "artifact_type": "cards.normalized",
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "source_file": str(cards_raw_path),
        "items": normalized_cards,
        "stats": {"count": len(normalized_cards)},
    }
    decks_payload = {
        "artifact_type": "decks.normalized",
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "source_file": str(decks_raw_path),
        "overview": overview,
        "items": normalized_decks,
        "stats": {"count": len(normalized_decks)},
    }
    deck_cards_payload = {
        "artifact_type": "deck_cards.normalized",
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "source_file": str(decks_raw_path),
        "items": normalized_deck_cards,
        "stats": {"count": len(normalized_deck_cards)},
    }

    validate_payload(cards_payload, "cards.normalized")
    validate_payload(decks_payload, "decks.normalized")
    validate_payload(deck_cards_payload, "deck_cards.normalized")

    write_json(cards_output_path, cards_payload)
    write_json(decks_output_path, decks_payload)
    write_json(deck_cards_output_path, deck_cards_payload)

    issues = _top_level_contract_issues(cards_payload, decks_payload, deck_cards_payload)
    issues.extend(
        _content_validation_issues(
            normalized_cards,
            normalized_decks,
            normalized_deck_cards,
        )
    )
    status = _validation_status(issues)

    checks = {
        "cards_raw_exists": cards_raw_path.exists(),
        "decks_raw_exists": decks_raw_path.exists(),
        "cards_normalized_count": len(normalized_cards),
        "decks_normalized_count": len(normalized_decks),
        "deck_cards_normalized_count": len(normalized_deck_cards),
    }

    warnings = [issue["message"] for issue in issues if issue.get("severity") == "warning"]
    errors = [issue["message"] for issue in issues if issue.get("severity") == "error"]

    validation_payload = {
        "artifact_type": "validation.report",
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": date_value,
        "generated_at": _utc_now_iso(),
        "status": status,
        "checks": checks,
        "issues": issues,
        "outputs": {
            "cards": str(cards_output_path),
            "decks": str(decks_output_path),
            "deck_cards": str(deck_cards_output_path),
        },
        "summary": {
            "error_count": len(errors),
            "warning_count": len(warnings),
            "info_count": len([issue for issue in issues if issue.get("severity") == "info"]),
        },
    }
    validate_payload(validation_payload, "validation.report")
    write_json(validation_output_path, validation_payload)

    return {
        "snapshot_date": date_value,
        "status": status,
        "outputs": validation_payload["outputs"],
        "counts": {
            "cards": len(normalized_cards),
            "decks": len(normalized_decks),
            "deck_cards": len(normalized_deck_cards),
        },
        "warnings": warnings,
        "errors": errors,
        "validation_report": str(validation_output_path),
    }
