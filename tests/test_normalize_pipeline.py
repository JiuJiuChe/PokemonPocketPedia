from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pokepocketpedia.normalize.pipeline import run_normalize


def _write_raw_snapshot(raw_root: Path) -> None:
    cards_dir = raw_root / "cards" / "2026-02-08"
    decks_dir = raw_root / "decks" / "2026-02-08"
    cards_dir.mkdir(parents=True, exist_ok=True)
    decks_dir.mkdir(parents=True, exist_ok=True)

    cards_payload = {
        "snapshot_date": "2026-02-08",
        "cards": [
            {
                "id": "A1-001",
                "localId": "001",
                "name": "Bulbasaur",
                "category": "Pokemon",
                "set": {"id": "A1", "name": "Genetic Apex"},
                "rarity": "Common",
                "hp": 70,
                "types": ["Grass"],
                "attacks": [{"name": "Tackle", "cost": ["Colorless"], "damage": "10"}],
                "boosters": [{"id": "A1", "name": "Genetic Apex"}],
            }
        ],
    }

    decks_payload = {
        "snapshot_date": "2026-02-08",
        "overview": {
            "game": "POCKET",
            "format": "STANDARD",
            "set_code": "B2",
            "set_name": "Fantastical Parade",
            "tournaments": 65,
            "players": 9831,
            "matches": 26255,
        },
        "decks": [
            {
                "rank": 1,
                "deck_name": "Hydreigon Mega Absol ex",
                "slug": "hydreigon-mega-absol-ex-b1",
                "count": 1487,
                "share_pct": 15.13,
                "win_rate_pct": 53.43,
                "match_record": "4679 - 3817 - 261",
                "deck_url": "https://play.limitlesstcg.com/decks/hydreigon-mega-absol-ex-b1",
                "matchups_url": "https://play.limitlesstcg.com/decks/hydreigon-mega-absol-ex-b1/matchups",
                "icons": ["https://example.com/a.png"],
                "is_hidden_by_default": False,
                "sample_decklist_url": "https://play.limitlesstcg.com/tournament/test/player/alice/decklist",
                "sample_deck_cards": [
                    {
                        "name": "Deino",
                        "set_code": "B1",
                        "number": "155",
                        "card_id": "B1-155",
                        "card_url": "https://pocket.limitlesstcg.com/cards/B1/155",
                        "sample_count": 2,
                        "present_in_samples": 2,
                        "presence_rate": 1.0,
                        "total_count": 3,
                        "avg_count": 1.5,
                    }
                ],
            }
        ],
    }

    (cards_dir / "cards.json").write_text(json.dumps(cards_payload), encoding="utf-8")
    (decks_dir / "decks.json").write_text(json.dumps(decks_payload), encoding="utf-8")


def test_run_normalize_writes_outputs(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    processed_root = tmp_path / "processed"
    _write_raw_snapshot(raw_root)

    report = run_normalize(
        raw_root=raw_root,
        processed_root=processed_root,
        snapshot_date=date(2026, 2, 8),
    )

    assert report["status"] == "ok"
    assert report["counts"]["cards"] == 1
    assert report["counts"]["decks"] == 1
    assert report["counts"]["deck_cards"] == 1

    cards_file = processed_root / "cards" / "2026-02-08" / "cards.normalized.json"
    decks_file = processed_root / "decks" / "2026-02-08" / "decks.normalized.json"
    deck_cards_file = processed_root / "decks" / "2026-02-08" / "deck_cards.normalized.json"
    validation_file = processed_root / "validation" / "2026-02-08" / "report.json"

    assert cards_file.exists()
    assert decks_file.exists()
    assert deck_cards_file.exists()
    assert validation_file.exists()

    cards_payload = json.loads(cards_file.read_text(encoding="utf-8"))
    decks_payload = json.loads(decks_file.read_text(encoding="utf-8"))

    assert cards_payload["items"][0]["card_id"] == "A1-001"
    assert cards_payload["items"][0]["hp"] == 70
    assert decks_payload["items"][0]["deck_name"] == "Hydreigon Mega Absol ex"

    deck_cards_payload = json.loads(deck_cards_file.read_text(encoding="utf-8"))
    assert deck_cards_payload["items"][0]["deck_slug"] == "hydreigon-mega-absol-ex-b1"
    assert deck_cards_payload["items"][0]["card_id"] == "B1-155"
    assert deck_cards_payload["items"][0]["avg_count"] == 1.5


def test_run_normalize_missing_raw_raises(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    processed_root = tmp_path / "processed"

    try:
        run_normalize(
            raw_root=raw_root,
            processed_root=processed_root,
            snapshot_date=date(2026, 2, 8),
        )
    except FileNotFoundError as exc:
        assert "Missing cards raw snapshot" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError for missing raw snapshot")
