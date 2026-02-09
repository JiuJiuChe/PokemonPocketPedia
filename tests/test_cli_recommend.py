from __future__ import annotations

import json
import sys
from pathlib import Path

from pokepocketpedia import cli


def test_recommend_json_only_writes_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli,
        "build_recommendation_context",
        lambda deck_slug, snapshot_date=None, key_card_limit=12: {
            "snapshot_date": "2026-02-09",
            "deck_slug": deck_slug,
            "context_payload": {},
            "llm_input": {
                "context": {
                    "target_deck": {"deck_name": "Hydreigon Mega Absol ex"},
                    "deck_card_grid": [],
                }
            },
        },
    )
    monkeypatch.setattr(
        cli,
        "generate_recommendation",
        lambda llm_input, provider="anthropic", model=None: {
            "provider": provider,
            "model": model or "claude-sonnet-4-5-20250929",
            "generated_at": "2026-02-09T00:00:00+00:00",
            "structured_output": {
                "deck_gameplan": "Test plan",
                "key_cards_and_roles": [],
                "opening_plan": "Open",
                "midgame_plan": "Mid",
                "closing_plan": "Close",
                "tech_choices": [],
                "common_pitfalls": [],
                "confidence_and_limitations": "OK",
            },
            "raw_text": "",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pokepocketpedia-recommend",
            "--format",
            "json",
            "--deck-slug",
            "hydreigon-mega-absol-ex-b1",
        ],
    )

    exit_code = cli.recommend()
    assert exit_code == 0

    report_dir = tmp_path / "data" / "processed" / "reports" / "2026-02-09"
    json_path = report_dir / "recommendation.hydreigon-mega-absol-ex-b1.json"
    md_path = report_dir / "recommendation.hydreigon-mega-absol-ex-b1.md"
    html_path = report_dir / "recommendation.hydreigon-mega-absol-ex-b1.html"
    assert json_path.exists()
    assert not md_path.exists()
    assert not html_path.exists()


def test_render_recommendation_report_from_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    report_dir = tmp_path / "data" / "processed" / "reports" / "2026-02-09"
    report_dir.mkdir(parents=True, exist_ok=True)
    input_path = report_dir / "recommendation.hydreigon-mega-absol-ex-b1.json"
    bundle = {
        "snapshot_date": "2026-02-09",
        "deck_slug": "hydreigon-mega-absol-ex-b1",
        "context_payload": {
            "snapshot_date": "2026-02-09",
            "deck_slug": "hydreigon-mega-absol-ex-b1",
            "llm_input": {
                "context": {
                    "target_deck": {"deck_name": "Hydreigon Mega Absol ex"},
                    "deck_card_grid": [],
                }
            },
        },
        "llm_result": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-5-20250929",
            "generated_at": "2026-02-09T00:00:00+00:00",
            "structured_output": {
                "deck_gameplan": "Test plan",
                "key_cards_and_roles": [],
                "opening_plan": "Open",
                "midgame_plan": "Mid",
                "closing_plan": "Close",
                "tech_choices": [],
                "common_pitfalls": [],
                "confidence_and_limitations": "OK",
            },
            "raw_text": "",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    }
    input_path.write_text(json.dumps(bundle), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pokepocketpedia-render-recommendation",
            "--input",
            str(input_path),
            "--format",
            "all",
        ],
    )
    exit_code = cli.render_recommendation_report()
    assert exit_code == 0

    md_path = report_dir / "recommendation.hydreigon-mega-absol-ex-b1.md"
    html_path = report_dir / "recommendation.hydreigon-mega-absol-ex-b1.html"
    assert md_path.exists()
    assert html_path.exists()
    assert "Deck Recommendation Report" in md_path.read_text(encoding="utf-8")
    assert "<html" in html_path.read_text(encoding="utf-8")
