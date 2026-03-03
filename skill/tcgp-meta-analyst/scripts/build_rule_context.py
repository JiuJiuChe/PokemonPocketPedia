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


def build_card_info(processed_root: Path, snapshot_date: str) -> dict[str, Any]:
    cards_payload = _read_json(processed_root / "cards" / snapshot_date / "cards.normalized.json")
    cards = [item for item in cards_payload.get("items", []) if isinstance(item, dict)]

    card_items: list[dict[str, Any]] = []
    for card in cards:
        card_items.append(
            {
                "card_id": card.get("card_id"),
                "name": card.get("name"),
                "category": card.get("category"),
                "trainer_type": card.get("trainer_type"),
                "types": card.get("types"),
                "stage": card.get("stage"),
                "hp": card.get("hp"),
                "ability_name": card.get("ability_name"),
                "ability_text": card.get("ability_text"),
                "attacks": card.get("attacks") if isinstance(card.get("attacks"), list) else [],
                "effect": card.get("effect"),
                "retreat": card.get("retreat"),
                "set_id": card.get("set_id"),
                "set_name": card.get("set_name"),
            }
        )

    return {
        "snapshot_date": snapshot_date,
        "artifact_sources": {
            "cards": str(processed_root / "cards" / snapshot_date / "cards.normalized.json"),
        },
        "cards": card_items,
    }


def build_top_decks_info(processed_root: Path, snapshot_date: str, top_n_decks: int) -> dict[str, Any]:
    decks_payload = _read_json(processed_root / "decks" / snapshot_date / "decks.normalized.json")
    deck_cards_payload = _read_json(
        processed_root / "decks" / snapshot_date / "deck_cards.normalized.json"
    )

    deck_items = [item for item in decks_payload.get("items", []) if isinstance(item, dict)]
    deck_rows = [item for item in deck_cards_payload.get("items", []) if isinstance(item, dict)]

    deck_stats_by_slug: dict[str, dict[str, Any]] = {}
    for deck in deck_items:
        slug = str(deck.get("slug") or "").strip()
        if not slug:
            continue
        deck_stats_by_slug[slug] = {
            "deck_name": deck.get("deck_name"),
            "rank": deck.get("rank"),
            "share_pct": deck.get("share_pct"),
            "win_rate_pct": deck.get("win_rate_pct"),
            "count": deck.get("count"),
            "players": deck.get("players"),
            "matches": deck.get("matches"),
            "match_record": deck.get("match_record"),
            "set_code": deck.get("set_code"),
            "set_name": deck.get("set_name"),
        }

    deck_score: dict[str, float] = {}
    deck_name: dict[str, str] = {}
    for row in deck_rows:
        slug = str(row.get("deck_slug") or "").strip()
        if not slug:
            continue
        deck_name[slug] = str(row.get("deck_name") or slug)
        score = _safe_float(row.get("presence_rate")) * _safe_float(row.get("avg_count"))
        deck_score[slug] = deck_score.get(slug, 0.0) + score

    for slug, deck_stats in deck_stats_by_slug.items():
        if slug not in deck_name:
            deck_name[slug] = str(deck_stats.get("deck_name") or slug)
        if slug not in deck_score:
            deck_score[slug] = 0.0
        deck_score[slug] += (_safe_float(deck_stats.get("share_pct")) / 100.0) + (
            _safe_float(deck_stats.get("win_rate_pct")) / 100.0
        )

    top_slugs = [
        slug
        for slug, _ in sorted(
            deck_score.items(),
            key=lambda pair: pair[1],
            reverse=True,
        )[:top_n_decks]
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
            key_cards.append(
                {
                    "card_id": card_id or None,
                    "card_name": row.get("card_name"),
                    "avg_count": row.get("avg_count"),
                    "presence_rate": row.get("presence_rate"),
                }
            )

        decks_compact.append(
            {
                "deck_slug": slug,
                "deck_name": deck_name.get(slug, slug),
                "deck_stats": deck_stats_by_slug.get(slug, {}),
                "key_cards": key_cards,
            }
        )

    return {
        "snapshot_date": snapshot_date,
        "artifact_sources": {
            "decks": str(processed_root / "decks" / snapshot_date / "decks.normalized.json"),
            "deck_cards": str(
                processed_root / "decks" / snapshot_date / "deck_cards.normalized.json"
            ),
        },
        "rule_profile": "pokemon-tcg-pocket",
        "decks": decks_compact,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="build_rule_context")
    parser.add_argument("--processed-root", default="data/processed")
    parser.add_argument("--snapshot-date", default=None)
    parser.add_argument("--top-n-decks", type=int, default=10)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    processed_root = Path(args.processed_root)
    snapshot_date = _resolve_snapshot(processed_root, args.snapshot_date)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    card_info = build_card_info(processed_root, snapshot_date)
    top_decks_info = build_top_decks_info(processed_root, snapshot_date, max(args.top_n_decks, 1))

    card_info_path = out_dir / "card_info.json"
    top_decks_info_path = out_dir / "top_decks_info.json"
    card_info_path.write_text(
        json.dumps(card_info, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    top_decks_info_path.write_text(
        json.dumps(top_decks_info, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"[build_rule_context] wrote: {card_info_path}")
    print(f"[build_rule_context] wrote: {top_decks_info_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
