#!/usr/bin/env python3
"""Build compact, rule-aware analysis context from processed TCGP artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _latest_snapshot(section_dir: Path) -> str:
    if not section_dir.exists():
        raise FileNotFoundError(f"Missing section dir: {section_dir}")
    values: list[date] = []
    for child in section_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            values.append(date.fromisoformat(child.name))
        except ValueError:
            continue
    if not values:
        raise FileNotFoundError(f"No snapshots found under {section_dir}")
    return max(values).isoformat()


def _resolve_snapshot(processed_root: Path, requested: str | None) -> str:
    if requested:
        return requested
    cards_dir = processed_root / "cards"
    decks_dir = processed_root / "decks"
    cards_latest = _latest_snapshot(cards_dir)
    decks_latest = _latest_snapshot(decks_dir)
    return min(cards_latest, decks_latest)


def _safe_float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip().replace("%", "")
        try:
            return float(raw)
        except ValueError:
            return 0.0
    return 0.0


def build_context(processed_root: Path, snapshot_date: str, top_n_decks: int) -> dict[str, Any]:
    cards_payload = _read_json(processed_root / "cards" / snapshot_date / "cards.normalized.json")
    deck_cards_payload = _read_json(
        processed_root / "decks" / snapshot_date / "deck_cards.normalized.json"
    )

    cards = [item for item in cards_payload.get("items", []) if isinstance(item, dict)]
    deck_rows = [item for item in deck_cards_payload.get("items", []) if isinstance(item, dict)]

    cards_by_id: dict[str, dict[str, Any]] = {}
    for card in cards:
        card_id = str(card.get("card_id") or "").strip()
        if card_id:
            cards_by_id[card_id.casefold()] = card

    deck_score: dict[str, float] = {}
    deck_name: dict[str, str] = {}
    for row in deck_rows:
        slug = str(row.get("deck_slug") or "").strip()
        if not slug:
            continue
        deck_name[slug] = str(row.get("deck_name") or slug)
        score = _safe_float(row.get("presence_rate")) * _safe_float(row.get("avg_count"))
        deck_score[slug] = deck_score.get(slug, 0.0) + score

    top_slugs = [
        slug
        for slug, _ in sorted(deck_score.items(), key=lambda pair: pair[1], reverse=True)[:top_n_decks]
    ]

    decks_compact: list[dict[str, Any]] = []
    for slug in top_slugs:
        rows = [r for r in deck_rows if str(r.get("deck_slug") or "") == slug]
        rows.sort(
            key=lambda r: (
                -_safe_float(r.get("presence_rate")),
                -_safe_float(r.get("avg_count")),
                str(r.get("card_name") or ""),
            )
        )
        key_cards: list[dict[str, Any]] = []
        for row in rows[:12]:
            card_id = str(row.get("card_id") or "")
            card = cards_by_id.get(card_id.casefold()) if card_id else None
            key_cards.append(
                {
                    "card_id": card_id or None,
                    "card_name": row.get("card_name"),
                    "avg_count": row.get("avg_count"),
                    "presence_rate": row.get("presence_rate"),
                    "category": card.get("category") if isinstance(card, dict) else None,
                    "trainer_type": card.get("trainer_type") if isinstance(card, dict) else None,
                    "attacks": card.get("attacks") if isinstance(card, dict) else [],
                    "ability_text": card.get("ability_text") if isinstance(card, dict) else None,
                    "effect": card.get("effect") if isinstance(card, dict) else None,
                    "retreat": card.get("retreat") if isinstance(card, dict) else None,
                }
            )

        decks_compact.append(
            {
                "deck_slug": slug,
                "deck_name": deck_name.get(slug, slug),
                "key_cards": key_cards,
            }
        )

    return {
        "snapshot_date": snapshot_date,
        "artifact_sources": {
            "cards": str(processed_root / "cards" / snapshot_date / "cards.normalized.json"),
            "deck_cards": str(processed_root / "decks" / snapshot_date / "deck_cards.normalized.json"),
        },
        "rule_profile": "pokemon-tcg-pocket",
        "decks": decks_compact,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="build_rule_context")
    parser.add_argument("--processed-root", default="data/processed")
    parser.add_argument("--snapshot-date", default=None)
    parser.add_argument("--top-n-decks", type=int, default=10)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    processed_root = Path(args.processed_root)
    snapshot_date = _resolve_snapshot(processed_root, args.snapshot_date)
    payload = build_context(processed_root, snapshot_date, max(args.top_n_decks, 1))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"[build_rule_context] wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
