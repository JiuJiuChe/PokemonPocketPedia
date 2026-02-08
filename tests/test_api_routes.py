from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from pokepocketpedia.api.main import app


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_processed(processed_root: Path) -> None:
    cards_08 = {
        "items": [
            {"card_id": "A1-001", "name": "Bulbasaur", "set_id": "A1", "ability_text": "Grow"},
            {"card_id": "A1-004", "name": "Charmander", "set_id": "A1", "effect": "Fire Tail"},
        ]
    }
    cards_09 = {
        "items": [
            {"card_id": "B1-155", "name": "Deino", "set_id": "B1", "ability_text": "Dark path"},
            {"card_id": "B1-157", "name": "Hydreigon", "set_id": "B1", "ability_text": "Dark aura"},
        ]
    }
    decks_09 = {
        "items": [
            {
                "deck_name": "Hydreigon Mega Absol ex",
                "slug": "hydreigon-mega-absol-ex-b1",
                "share_pct": 15.13,
                "count": 1487,
            },
            {
                "deck_name": "Mega Altaria ex Chingling",
                "slug": "mega-altaria-ex-chingling-b1",
                "share_pct": 6.04,
                "count": 594,
            },
        ]
    }
    top_decks = {
        "items": [
            {
                "deck_name": "Hydreigon Mega Absol ex",
                "slug": "hydreigon-mega-absol-ex-b1",
                "share_pct": 15.13,
                "win_rate_pct": 53.43,
            }
        ]
    }
    top_cards = {
        "items": [
            {
                "card_id": "B1-157",
                "card_name": "Hydreigon",
                "weighted_share_points": 2.0,
                "decks_seen": 10,
                "avg_presence_rate": 0.9,
            },
            {
                "card_id": "B1-155",
                "card_name": "Deino",
                "weighted_share_points": 1.5,
                "decks_seen": 9,
                "avg_presence_rate": 0.8,
            },
        ]
    }
    top_cards_by_archetype = {
        "items": [
            {
                "deck_slug": "hydreigon-mega-absol-ex-b1",
                "deck_name": "Hydreigon Mega Absol ex",
                "share_pct": 15.13,
                "top_cards": [{"card_id": "B1-157", "card_name": "Hydreigon", "avg_count": 2.0}],
            }
        ]
    }
    trends = {
        "artifact_type": "meta_metrics.trends_1d_7d",
        "reference_dates": {
            "one_day": "2026-02-08",
            "seven_day": "2026-02-02",
            "one_day_available": True,
            "seven_day_available": False,
            "one_day_reference": "2026-02-08",
            "seven_day_reference": None,
        },
        "decks": [
            {
                "deck_slug": "hydreigon-mega-absol-ex-b1",
                "delta_share_pct_1d": 0.5,
                "delta_share_pct_7d": None,
            }
        ],
        "cards": [],
        "stats": {"deck_count": 1, "card_count": 0},
    }
    overview = {
        "artifact_type": "meta_metrics.overview",
        "inputs": {"cards_count": 2, "decks_count": 2, "deck_cards_count": 10},
        "highlights": {
            "most_popular_deck": top_decks["items"][0],
            "most_popular_card": top_cards["items"][0],
        },
    }

    _write_json(processed_root / "cards" / "2026-02-08" / "cards.normalized.json", cards_08)
    _write_json(processed_root / "cards" / "2026-02-09" / "cards.normalized.json", cards_09)
    _write_json(processed_root / "decks" / "2026-02-09" / "decks.normalized.json", decks_09)
    _write_json(processed_root / "meta_metrics" / "2026-02-09" / "top_decks.json", top_decks)
    _write_json(processed_root / "meta_metrics" / "2026-02-09" / "top_cards.json", top_cards)
    _write_json(
        processed_root / "meta_metrics" / "2026-02-09" / "top_cards_by_archetype.json",
        top_cards_by_archetype,
    )
    _write_json(processed_root / "meta_metrics" / "2026-02-09" / "trends_1d_7d.json", trends)
    _write_json(processed_root / "meta_metrics" / "2026-02-09" / "overview.json", overview)


def test_cards_endpoint_latest_filter_pagination(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    client = TestClient(app)
    response = client.get("/cards?q=hyd&limit=1&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_date"] == "2026-02-09"
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["card_id"] == "B1-157"


def test_decks_endpoint_filters(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    client = TestClient(app)
    response = client.get("/decks?min_share_pct=10")
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_date"] == "2026-02-09"
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "hydreigon-mega-absol-ex-b1"


def test_metrics_endpoints(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    client = TestClient(app)
    decks_res = client.get("/metrics/top-decks")
    cards_res = client.get("/metrics/top-cards?limit=1")
    arch_res = client.get("/metrics/top-cards-by-archetype?deck_slug=hydreigon-mega-absol-ex-b1")
    trend_res = client.get("/metrics/trends")
    overview_res = client.get("/metrics/overview")

    assert decks_res.status_code == 200
    assert cards_res.status_code == 200
    assert arch_res.status_code == 200
    assert trend_res.status_code == 200
    assert overview_res.status_code == 200
    assert decks_res.json()["items"][0]["slug"] == "hydreigon-mega-absol-ex-b1"
    assert len(cards_res.json()["items"]) == 1
    assert arch_res.json()["total"] == 1
    assert trend_res.json()["artifact_type"] == "meta_metrics.trends_1d_7d"
    assert overview_res.json()["artifact_type"] == "meta_metrics.overview"


def test_recommendations_endpoint(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    client = TestClient(app)
    response = client.get("/recommendations/latest?top_n=2")
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_date"] == "2026-02-09"
    assert len(body["recommendations"]) == 1
    assert len(body["tech_cards"]) == 2


def test_snapshot_not_found_returns_404(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    client = TestClient(app)
    response = client.get("/metrics/top-decks?snapshot_date=2026-01-01")
    assert response.status_code == 404
