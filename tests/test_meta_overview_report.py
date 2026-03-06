from __future__ import annotations

import json
from pathlib import Path

from pokepocketpedia.report.meta_overview import render_meta_overview_report


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_render_meta_overview_report(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    reports = tmp_path / "reports"
    snapshot = "2026-02-09"

    _write_json(
        processed / "meta_metrics" / snapshot / "top_decks.json",
        {
            "items": [
                {
                    "deck_name": "Hydreigon Mega Absol ex",
                    "slug": "hydreigon-mega-absol-ex-b1",
                    "count": 120,
                    "win_rate_pct": 53.39,
                },
                {
                    "deck_name": "Low Win Deck",
                    "slug": "low-win-deck",
                    "count": 300,
                    "win_rate_pct": 44.0,
                },
            ]
        },
    )
    _write_json(
        processed / "meta_metrics" / snapshot / "top_cards.json",
        {
            "items": [
                {
                    "card_id": "B1-157",
                    "card_name": "Hydreigon",
                    "avg_presence_rate": 0.85,
                    "weighted_share_points": 1.234,
                },
                {
                    "card_id": "P-A-7",
                    "card_name": "Professor's Research",
                    "avg_presence_rate": 0.95,
                    "weighted_share_points": 1.5,
                },
            ]
        },
    )
    _write_json(
        processed / "decks" / snapshot / "deck_cards.normalized.json",
        {
            "items": [
                {
                    "deck_slug": "hydreigon-mega-absol-ex-b1",
                    "card_id": "B1-157",
                    "card_name": "Hydreigon",
                    "avg_count": 2.0,
                    "presence_rate": 1.0,
                },
                {
                    "deck_slug": "hydreigon-mega-absol-ex-b1",
                    "card_id": "B1-155",
                    "card_name": "Deino",
                    "avg_count": 2.0,
                    "presence_rate": 1.0,
                },
            ]
        },
    )
    _write_json(
        processed / "cards" / snapshot / "cards.normalized.json",
        {
            "items": [
                {"card_id": "B1-157", "name": "Hydreigon", "image": "https://assets.tcgdex.net/en/tcgp/B1/157"},
                {"card_id": "B1-155", "name": "Deino", "image": "https://assets.tcgdex.net/en/tcgp/B1/155"},
                {"card_id": "P-A-7", "name": "Professor's Research", "image": "https://assets.tcgdex.net/en/tcgp/P-A/007"},
            ]
        },
    )

    (reports / snapshot).mkdir(parents=True, exist_ok=True)
    (reports / snapshot / "recommendation.hydreigon-mega-absol-ex-b1.html").write_text(
        "<html></html>",
        encoding="utf-8",
    )

    output = render_meta_overview_report(
        processed_root=processed,
        reports_root=reports,
        snapshot_date=snapshot,
    )
    assert output.exists()
    html = output.read_text(encoding="utf-8")
    assert "Week 02/09/2026 Pokemon TCGP Meta Overview" in html
    assert "Meta Overview Summary" in html
    assert "Current Highlights" in html
    assert "Changes vs Previous" in html
    assert "Top 10 Popular Decks" in html
    assert "Top 10 Popular Cards" in html
    assert "<th>Count</th>" in html
    assert ">300<" in html
    assert 'href="recommendation.hydreigon-mega-absol-ex-b1.html"' in html
    assert "win-hot" in html
    assert "win-cold" in html
    assert "Pick rate: 85.0%" in html
    assert "Auto fallback summary (LLM unavailable)." in html
    assert "Snapshot:" not in html
    assert html.find("Low Win Deck") < html.find("Hydreigon Mega Absol ex")


def test_render_meta_overview_report_with_openclaw_summary(tmp_path: Path, monkeypatch) -> None:
    processed = tmp_path / "processed"
    reports = tmp_path / "reports"
    snapshot = "2026-03-05"

    _write_json(
        processed / "meta_metrics" / snapshot / "top_decks.json",
        {"items": [{"deck_name": "Deck A", "slug": "deck-a", "count": 111, "win_rate_pct": 52.1}]},
    )
    _write_json(
        processed / "meta_metrics" / snapshot / "top_cards.json",
        {"items": [{"card_id": "A-1", "card_name": "Card A", "avg_presence_rate": 0.75}]},
    )
    _write_json(
        processed / "decks" / snapshot / "deck_cards.normalized.json",
        {"items": [{"deck_slug": "deck-a", "card_id": "A-1", "card_name": "Card A", "avg_count": 2.0, "presence_rate": 1.0}]},
    )
    _write_json(
        processed / "cards" / snapshot / "cards.normalized.json",
        {"items": [{"card_id": "A-1", "name": "Card A", "image": "https://assets.tcgdex.net/en/tcgp/A/001"}]},
    )

    summary_payload = {
        "summary": "OpenClaw summary is available.",
        "current_highlights": ["Deck A leads."],
        "changes_vs_previous": ["No major shifts."],
    }

    class _Proc:
        returncode = 0
        stdout = json.dumps({"payloads": [{"text": json.dumps(summary_payload)}]})
        stderr = ""

    from pokepocketpedia.report import meta_overview

    def _fake_run(*args, **kwargs):
        return _Proc()

    monkeypatch.setattr(meta_overview.subprocess, "run", _fake_run)

    output = render_meta_overview_report(
        processed_root=processed,
        reports_root=reports,
        snapshot_date=snapshot,
        summary_provider="openclaw",
    )
    html = output.read_text(encoding="utf-8")
    assert "OpenClaw summary is available." in html
    assert "Auto fallback summary (LLM unavailable)." not in html


def test_render_meta_overview_report_falls_back_to_card_page_image(tmp_path: Path, monkeypatch) -> None:
    processed = tmp_path / "processed"
    reports = tmp_path / "reports"
    snapshot = "2026-03-06"

    _write_json(
        processed / "meta_metrics" / snapshot / "top_decks.json",
        {"items": [{"deck_name": "Deck A", "slug": "deck-a", "count": 120, "win_rate_pct": 53.0}]},
    )
    _write_json(
        processed / "meta_metrics" / snapshot / "top_cards.json",
        {
            "items": [
                {
                    "card_id": "B2a-36",
                    "card_name": "Baxcalibur",
                    "avg_presence_rate": 0.8,
                    "weighted_share_points": 1.2,
                    "card_url": "https://pocket.limitlesstcg.com/cards/B2a/36",
                }
            ]
        },
    )
    _write_json(
        processed / "decks" / snapshot / "deck_cards.normalized.json",
        {
            "items": [
                {
                    "deck_slug": "deck-a",
                    "card_id": "B2a-36",
                    "card_name": "Baxcalibur",
                    "avg_count": 2.0,
                    "presence_rate": 1.0,
                    "card_url": "https://pocket.limitlesstcg.com/cards/B2a/36",
                }
            ]
        },
    )
    _write_json(
        processed / "cards" / snapshot / "cards.normalized.json",
        {"items": []},
    )

    from pokepocketpedia.report import meta_overview

    monkeypatch.setattr(
        meta_overview,
        "_image_from_card_page",
        lambda url: "https://assets.limitlesstcg.com/fallback/baxcalibur.webp",
    )

    output = render_meta_overview_report(
        processed_root=processed,
        reports_root=reports,
        snapshot_date=snapshot,
    )
    html = output.read_text(encoding="utf-8")
    assert "https://assets.limitlesstcg.com/fallback/baxcalibur.webp" in html
    assert "No Image" not in html
