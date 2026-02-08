from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pokepocketpedia.analyze.pipeline import run_analyze


def _write_processed_snapshot(processed_root: Path, snapshot: str = "2026-02-08") -> None:
    cards_dir = processed_root / "cards" / snapshot
    decks_dir = processed_root / "decks" / snapshot
    cards_dir.mkdir(parents=True, exist_ok=True)
    decks_dir.mkdir(parents=True, exist_ok=True)

    cards_payload = {
        "snapshot_date": snapshot,
        "items": [
            {"card_id": "B1-155", "name": "Deino"},
            {"card_id": "B1-157", "name": "Hydreigon"},
        ],
    }

    decks_payload = {
        "snapshot_date": snapshot,
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
        "snapshot_date": snapshot,
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


def _write_prior_metrics(processed_root: Path, snapshot: str = "2026-02-07") -> None:
    metrics_dir = processed_root / "meta_metrics" / snapshot
    metrics_dir.mkdir(parents=True, exist_ok=True)

    top_decks = {
        "items": [
            {
                "slug": "hydreigon-mega-absol-ex-b1",
                "deck_name": "Hydreigon Mega Absol ex",
                "share_pct": 14.0,
            }
        ]
    }
    top_cards = {
        "items": [
            {
                "card_id": "B1-157",
                "card_name": "Hydreigon",
                "weighted_share_points": 1.0,
            }
        ]
    }

    (metrics_dir / "top_decks.json").write_text(json.dumps(top_decks), encoding="utf-8")
    (metrics_dir / "top_cards.json").write_text(json.dumps(top_cards), encoding="utf-8")


def test_run_analyze_writes_metrics(tmp_path: Path) -> None:
    processed_root = tmp_path / "processed"
    _write_processed_snapshot(processed_root)

    report = run_analyze(processed_root=processed_root, snapshot_date=date(2026, 2, 8))
    assert report["status"] == "ok_with_warnings"
    assert report["counts"]["top_decks"] == 2
    assert report["counts"]["top_cards"] == 2
    assert report["counts"]["top_cards_by_archetype"] == 2

    top_decks_file = processed_root / "meta_metrics" / "2026-02-08" / "top_decks.json"
    top_cards_file = processed_root / "meta_metrics" / "2026-02-08" / "top_cards.json"
    top_cards_by_archetype_file = (
        processed_root / "meta_metrics" / "2026-02-08" / "top_cards_by_archetype.json"
    )
    trends_file = processed_root / "meta_metrics" / "2026-02-08" / "trends_1d_7d.json"
    overview_file = processed_root / "meta_metrics" / "2026-02-08" / "overview.json"

    assert top_decks_file.exists()
    assert top_cards_file.exists()
    assert top_cards_by_archetype_file.exists()
    assert trends_file.exists()
    assert overview_file.exists()

    top_decks_payload = json.loads(top_decks_file.read_text(encoding="utf-8"))
    top_cards_payload = json.loads(top_cards_file.read_text(encoding="utf-8"))
    top_cards_by_archetype_payload = json.loads(
        top_cards_by_archetype_file.read_text(encoding="utf-8")
    )

    assert top_decks_payload["items"][0]["deck_name"] == "Hydreigon Mega Absol ex"
    assert top_cards_payload["items"][0]["card_name"] == "Hydreigon"
    assert top_cards_by_archetype_payload["items"][0]["deck_slug"] == "hydreigon-mega-absol-ex-b1"


def test_run_analyze_trends_with_prior_snapshot(tmp_path: Path) -> None:
    processed_root = tmp_path / "processed"
    _write_processed_snapshot(processed_root, snapshot="2026-02-08")
    _write_prior_metrics(processed_root, snapshot="2026-02-07")

    report = run_analyze(processed_root=processed_root, snapshot_date=date(2026, 2, 8))
    assert report["status"] == "ok_with_warnings"

    trends_file = processed_root / "meta_metrics" / "2026-02-08" / "trends_1d_7d.json"
    trends_payload = json.loads(trends_file.read_text(encoding="utf-8"))

    assert trends_payload["reference_dates"]["one_day_available"] is True
    assert trends_payload["reference_dates"]["seven_day_available"] is False
    assert trends_payload["reference_dates"]["one_day_reference"] == "2026-02-07"
    assert trends_payload["reference_dates"]["seven_day_reference"] is None

    hydreigon_trend = trends_payload["decks"][0]
    assert hydreigon_trend["deck_slug"] == "hydreigon-mega-absol-ex-b1"
    assert hydreigon_trend["delta_share_pct_1d"] is not None


def test_run_analyze_trends_fallback_to_nearest_prior_snapshot(tmp_path: Path) -> None:
    processed_root = tmp_path / "processed"
    _write_processed_snapshot(processed_root, snapshot="2026-02-10")
    _write_prior_metrics(processed_root, snapshot="2026-02-08")

    report = run_analyze(processed_root=processed_root, snapshot_date=date(2026, 2, 10))
    assert report["status"] == "ok_with_warnings"

    trends_file = processed_root / "meta_metrics" / "2026-02-10" / "trends_1d_7d.json"
    trends_payload = json.loads(trends_file.read_text(encoding="utf-8"))

    assert trends_payload["reference_dates"]["one_day"] == "2026-02-09"
    assert trends_payload["reference_dates"]["one_day_available"] is True
    assert trends_payload["reference_dates"]["one_day_reference"] == "2026-02-08"
    assert trends_payload["reference_dates"]["seven_day"] == "2026-02-03"
    assert trends_payload["reference_dates"]["seven_day_available"] is False
    assert trends_payload["reference_dates"]["seven_day_reference"] is None

    hydreigon_trend = trends_payload["decks"][0]
    assert hydreigon_trend["delta_share_pct_1d"] is not None


def test_run_analyze_missing_input_raises(tmp_path: Path) -> None:
    processed_root = tmp_path / "processed"

    try:
        run_analyze(processed_root=processed_root, snapshot_date=date(2026, 2, 8))
    except FileNotFoundError as exc:
        assert "Missing processed input" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError for missing processed input")
