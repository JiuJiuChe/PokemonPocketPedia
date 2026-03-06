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
            {
                "card_id": "P-A-007",
                "name": "Professor's Research",
                "set_id": "P-A",
                "set_name": "Promos-A",
                "category": "Trainer",
                "trainer_type": "Supporter",
                "effect": "Draw 2 cards.",
                "image": "https://assets.tcgdex.net/en/tcgp/P-A/007",
                "types": [],
                "attacks": [],
            },
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
            {
                "card_id": "P-A-7",
                "card_name": "Professor's Research",
                "weighted_share_points": 1.7,
                "decks_seen": 12,
                "avg_presence_rate": 0.98,
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
    _write_json(
        processed_root / "decks" / "2026-02-09" / "deck_cards.normalized.json",
        {
            "items": [
                {
                    "deck_slug": "hydreigon-mega-absol-ex-b1",
                    "card_id": "B1-157",
                    "card_name": "Hydreigon",
                    "avg_count": 2.0,
                    "presence_rate": 1.0,
                    "sample_count": 5,
                    "card_url": "https://example.com/B1-157",
                },
                {
                    "deck_slug": "hydreigon-mega-absol-ex-b1",
                    "card_id": "B1-155",
                    "card_name": "Deino",
                    "avg_count": 2.0,
                    "presence_rate": 1.0,
                    "sample_count": 5,
                    "card_url": "https://example.com/B1-155",
                },
                {
                    "deck_slug": "hydreigon-mega-absol-ex-b1",
                    "card_id": "P-A-7",
                    "card_name": "Professor's Research",
                    "avg_count": 2.0,
                    "presence_rate": 1.0,
                    "sample_count": 5,
                    "card_url": "https://example.com/P-A-7",
                },
            ]
        },
    )
    _write_json(processed_root / "meta_metrics" / "2026-02-09" / "top_decks.json", top_decks)
    _write_json(processed_root / "meta_metrics" / "2026-02-09" / "top_cards.json", top_cards)
    _write_json(
        processed_root / "meta_metrics" / "2026-02-09" / "top_cards_by_archetype.json",
        top_cards_by_archetype,
    )
    _write_json(processed_root / "meta_metrics" / "2026-02-09" / "trends_1d_7d.json", trends)
    _write_json(processed_root / "meta_metrics" / "2026-02-09" / "overview.json", overview)
    (processed_root / "reports" / "2026-02-09").mkdir(parents=True, exist_ok=True)
    (processed_root / "reports" / "2026-02-09" / "meta_overview.html").write_text(
        "<html>meta</html>",
        encoding="utf-8",
    )
    report_path = (
        processed_root
        / "reports"
        / "2026-02-09"
        / "recommendation.hydreigon-mega-absol-ex-b1.html"
    )
    report_path.write_text(
        "<html>deck</html>",
        encoding="utf-8",
    )


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


def test_recommendation_context_endpoint(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    client = TestClient(app)
    response = client.get(
        "/recommendations/context?deck_slug=hydreigon-mega-absol-ex-b1&key_card_limit=5"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_date"] == "2026-02-09"
    assert body["deck_slug"] == "hydreigon-mega-absol-ex-b1"
    assert body["context_version"] == "1.0.0"
    assert body["llm_input"]["context"]["target_deck"]["deck_name"] == "Hydreigon Mega Absol ex"
    assert len(body["llm_input"]["context"]["key_cards_from_samples"]) == 3


def test_recommendation_context_unknown_deck_404(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    client = TestClient(app)
    response = client.get("/recommendations/context?deck_slug=unknown-deck")
    assert response.status_code == 404


def test_recommendation_generate_endpoint(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    from pokepocketpedia.api.routes import recommendations as route_module

    def _fake_generate(
        llm_input: dict,
        provider: str = "anthropic",
        model: str | None = None,
    ) -> dict:
        return {
            "provider": provider,
            "model": model or "claude-sonnet-4-5-20250929",
            "generated_at": "2026-02-09T00:00:00+00:00",
            "structured_output": {
                "deck_gameplan": "Control tempo and preserve key evolutions.",
                "key_cards_and_roles": [],
                "opening_plan": "Set up basics quickly.",
                "midgame_plan": "Trade efficiently.",
                "closing_plan": "Sequence finisher safely.",
                "tech_choices": [],
                "common_pitfalls": [],
                "confidence_and_limitations": "Test output",
            },
            "raw_text": "{}",
            "usage": {"input_tokens": 100, "output_tokens": 200},
        }

    monkeypatch.setattr(route_module, "generate_recommendation", _fake_generate)

    client = TestClient(app)
    response = client.post(
        "/recommendations/generate",
        json={"deck_slug": "hydreigon-mega-absol-ex-b1", "provider": "anthropic"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "anthropic"
    assert body["deck_slug"] == "hydreigon-mega-absol-ex-b1"
    assert "deck_gameplan" in body["output"]


def test_snapshot_not_found_returns_404(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    client = TestClient(app)
    response = client.get("/metrics/top-decks?snapshot_date=2026-01-01")
    assert response.status_code == 404


def test_reports_latest_endpoint(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    client = TestClient(app)
    response = client.get("/reports/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_date"] == "2026-02-09"
    assert body["meta_overview"] == "/reports-static/2026-02-09/meta_overview.html"
    assert len(body["deck_reports"]) == 1

    snapshots_res = client.get("/reports/snapshots")
    assert snapshots_res.status_code == 200
    snapshots_body = snapshots_res.json()
    assert snapshots_body["total"] == 1
    assert snapshots_body["items"][0]["snapshot_date"] == "2026-02-09"


def test_interactive_llm_endpoints(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    from pokepocketpedia.api.routes import interactive as route_module

    seen_analysis_providers: list[str] = []
    seen_chat_providers: list[str] = []

    def _fake_interactive_analysis(
        llm_input: dict,
        mode: str,
        provider: str = "anthropic",
        model: str | None = None,
    ) -> dict:
        seen_analysis_providers.append(provider)
        return {
            "provider": provider,
            "model": model or "claude-sonnet-4-5-20250929",
            "generated_at": "2026-02-09T00:00:00+00:00",
            "output": {
                "executive_summary": f"mock-{mode}-summary",
                "composition_assessment": "ok",
                "consistency_assessment": "ok",
                "meta_matchups": "ok",
                "alternatives_and_risks": ["risk"],
                "completion_plan": "fill slots" if mode == "completion" else "",
                "recommended_additions": (
                    [{"card_name": "Copycat", "count": 1, "reason": "consistency"}]
                    if mode == "completion"
                    else []
                ),
                "confidence_and_limitations": "mock",
            },
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

    def _fake_chat_reply(
        context_input: dict,
        mode: str,
        history: list[dict],
        user_message: str,
        provider: str = "anthropic",
        model: str | None = None,
    ) -> dict:
        seen_chat_providers.append(provider)
        return {
            "provider": provider,
            "model": model or "claude-sonnet-4-5-20250929",
            "generated_at": "2026-02-09T00:00:00+00:00",
            "reply": f"mock-chat-{mode}: {user_message}",
            "usage": {"input_tokens": 11, "output_tokens": 9},
        }

    monkeypatch.setattr(route_module, "generate_interactive_analysis", _fake_interactive_analysis)
    monkeypatch.setattr(route_module, "generate_interactive_chat_reply", _fake_chat_reply)

    client = TestClient(app)
    eval_cards = [
        {"card_id": f"A1-{index:03d}", "count": 2}
        for index in range(1, 11)
    ]

    eval_res = client.post(
        "/interactive/evaluate-deck",
        json={"cards": eval_cards},
    )
    assert eval_res.status_code == 200
    assert eval_res.json()["status"] == "ok"
    assert eval_res.json()["mode"] == "evaluation"
    assert eval_res.json()["message"] == "mock-evaluation-summary"
    assert eval_res.json()["provider"] == "openclaw"

    complete_res = client.post(
        "/interactive/complete-deck",
        json={"cards": [{"card_id": "A1-001", "count": 2}]},
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "ok"
    assert complete_res.json()["mode"] == "completion"
    assert complete_res.json()["remaining_slots"] == 18
    assert complete_res.json()["provider"] == "openclaw"

    chat_res = client.post(
        "/interactive/chat-turn",
        json={
            "mode": "evaluation",
            "cards": eval_cards,
            "history": [{"role": "assistant", "content": "hello"}],
            "message": "what is the biggest risk?",
        },
    )
    assert chat_res.status_code == 200
    assert "mock-chat-evaluation" in chat_res.json()["reply"]
    assert chat_res.json()["provider"] == "openclaw"
    assert seen_analysis_providers == ["openclaw", "openclaw"]
    assert seen_chat_providers == ["openclaw"]

    template_res = client.get(
        "/interactive/deck-template?deck_slug=hydreigon-mega-absol-ex-b1"
    )
    assert template_res.status_code == 200
    template_body = template_res.json()
    assert template_body["deck_slug"] == "hydreigon-mega-absol-ex-b1"
    assert template_body["total_cards"] >= 1
    assert len(template_body["selected_cards"]) >= 1


def test_interactive_deck_card_details_endpoint(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    client = TestClient(app)
    response = client.post(
        "/interactive/deck-card-details",
        json={
            "cards": [
                {"card_id": "P-A-7", "count": 2},
                {"card_id": "B1-157", "count": 1},
                {"card_id": "UNKNOWN-999", "count": 1},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_date"] == "2026-02-09"
    assert body["requested_count"] == 3
    assert body["found_count"] == 2
    assert body["missing_card_ids"] == ["UNKNOWN-999"]

    first = body["items"][0]
    assert first["requested_card_id"] == "P-A-7"
    assert first["resolved_card_id"] == "P-A-007"
    assert first["name"] == "Professor's Research"
    assert first["image"] == "https://assets.tcgdex.net/en/tcgp/P-A/007/high.webp"
    assert first["usage"]["decks_seen"] == 12
    assert first["usage"]["sample_decks_seen"] == 1

    missing = body["items"][2]
    assert missing["found"] is False



def test_interactive_deck_card_details_fallback_image_from_card_page(tmp_path: Path, monkeypatch) -> None:
    processed_root = tmp_path / "processed"
    _seed_processed(processed_root)
    monkeypatch.setenv("POKEPOCKETPEDIA_PROCESSED_ROOT", str(processed_root))

    # Simulate new-card lag in cards catalog by removing one card doc.
    cards_path = processed_root / "cards" / "2026-02-09" / "cards.normalized.json"
    payload = json.loads(cards_path.read_text(encoding="utf-8"))
    payload["items"] = [
        item
        for item in payload.get("items", [])
        if not (isinstance(item, dict) and str(item.get("card_id")) == "B1-157")
    ]
    cards_path.write_text(json.dumps(payload), encoding="utf-8")

    from pokepocketpedia.common import image_utils

    monkeypatch.setattr(
        image_utils,
        "image_from_card_page",
        lambda card_url: "https://assets.limitlesstcg.com/fallback/from-card-page.webp",
    )

    client = TestClient(app)
    response = client.post(
        "/interactive/deck-card-details",
        json={"cards": [{"card_id": "B1-157", "count": 1}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["found_count"] == 1
    assert body["items"][0]["found"] is True
    assert body["items"][0]["image"] == "https://assets.limitlesstcg.com/fallback/from-card-page.webp"
