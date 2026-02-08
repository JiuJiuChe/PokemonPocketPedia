from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pokepocketpedia.analyze.pipeline import run_analyze


def _write_processed_snapshot(processed_root: Path) -> None:
    cards_dir = processed_root / "cards" / "2026-02-08"
    decks_dir = processed_root / "decks" / "2026-02-08"
    cards_dir.mkdir(parents=True, exist_ok=True)
    decks_dir.mkdir(parents=True, exist_ok=True)

    cards_payload = {
        "snapshot_date": "2026-02-08",
        "items": [
            {"card_id": "B1-155", "name": "Deino"},
            {"card_id": "B1-157", "name": "Hydreigon"},
        ],
    }

    decks_payload = {
        "snapshot_date": "2026-02-08",
        "items": [
            {
                "rank": 1,
                "deck_name": "Hydreigon Mega Absol ex",
                "slug": "hydreigon-mega-absol-ex-b1",
                "share_pct": 15.13,
                "count": 1487,
                "win_rate_pct": 53.43,
                "match_record": "4679 - 3817 - 261",
                "deck_url": "https://example.com/deck/1",
            },
            {
                "rank": 2,
                "deck_name": "Mega Altaria ex Chingling",
                "slug": "mega-altaria-ex-chingling-b1",
                "share_pct": 6.04,
                "count": 594,
                "win_rate_pct": 52.71,
                "match_record": "1839 - 1524 - 126",
                "deck_url": "https://example.com/deck/2",
            },
        ],
    }

    deck_cards_payload = {
        "snapshot_date": "2026-02-08",
        "items": [
            {
                "deck_slug": "hydreigon-mega-absol-ex-b1",
                "card_id": "B1-155",
                "card_name": "Deino",
                "card_set_code": "B1",
                "card_number": "155",
                "card_url": "https://example.com/card/deino",
                "avg_count": 1.5,
                "presence_rate": 1.0,
            },
            {
                "deck_slug": "hydreigon-mega-absol-ex-b1",
                "card_id": "B1-157",
                "card_name": "Hydreigon",
                "card_set_code": "B1",
                "card_number": "157",
                "card_url": "https://example.com/card/hydreigon",
                "avg_count": 2.0,
                "presence_rate": 1.0,
            },
            {
                "deck_slug": "mega-altaria-ex-chingling-b1",
                "card_id": "B1-155",
                "card_name": "Deino",
                "card_set_code": "B1",
                "card_number": "155",
                "card_url": "https://example.com/card/deino",
                "avg_count": 0.5,
                "presence_rate": 0.5,
            },
        ],
    }

    (cards_dir / "cards.normalized.json").write_text(json.dumps(cards_payload), encoding="utf-8")
    (decks_dir / "decks.normalized.json").write_text(json.dumps(decks_payload), encoding="utf-8")
    (decks_dir / "deck_cards.normalized.json").write_text(
        json.dumps(deck_cards_payload),
        encoding="utf-8",
    )


def test_run_analyze_writes_metrics(tmp_path: Path) -> None:
    processed_root = tmp_path / "processed"
    _write_processed_snapshot(processed_root)

    report = run_analyze(processed_root=processed_root, snapshot_date=date(2026, 2, 8))
    assert report["status"] == "ok"
    assert report["counts"]["top_decks"] == 2
    assert report["counts"]["top_cards"] == 2

    top_decks_file = processed_root / "meta_metrics" / "2026-02-08" / "top_decks.json"
    top_cards_file = processed_root / "meta_metrics" / "2026-02-08" / "top_cards.json"
    overview_file = processed_root / "meta_metrics" / "2026-02-08" / "overview.json"

    assert top_decks_file.exists()
    assert top_cards_file.exists()
    assert overview_file.exists()

    top_decks_payload = json.loads(top_decks_file.read_text(encoding="utf-8"))
    top_cards_payload = json.loads(top_cards_file.read_text(encoding="utf-8"))

    assert top_decks_payload["items"][0]["deck_name"] == "Hydreigon Mega Absol ex"
    assert top_cards_payload["items"][0]["card_name"] == "Hydreigon"


def test_run_analyze_missing_input_raises(tmp_path: Path) -> None:
    processed_root = tmp_path / "processed"

    try:
        run_analyze(processed_root=processed_root, snapshot_date=date(2026, 2, 8))
    except FileNotFoundError as exc:
        assert "Missing processed input" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError for missing processed input")
