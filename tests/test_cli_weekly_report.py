from __future__ import annotations

import json
import sys
from pathlib import Path

from pokepocketpedia import cli


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_weekly_report_reuses_previous_deck_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    snapshot = "2026-02-09"
    previous = "2026-02-08"
    slug = "hydreigon-mega-absol-ex-b1"

    _write_json(
        tmp_path / "data" / "processed" / "meta_metrics" / snapshot / "top_decks.json",
        {"items": [{"slug": slug, "count": 100}]},
    )
    previous_dir = tmp_path / "data" / "processed" / "reports" / previous
    previous_dir.mkdir(parents=True, exist_ok=True)
    (previous_dir / f"recommendation.{slug}.html").write_text("<html>old</html>", encoding="utf-8")

    render_calls: list[str | None] = []

    def _fake_render(snapshot_date: str | None = None) -> Path:
        render_calls.append(snapshot_date)
        return (
            tmp_path
            / "data"
            / "processed"
            / "reports"
            / snapshot
            / "meta_overview.html"
        )

    monkeypatch.setattr(cli, "render_meta_overview_report", _fake_render)

    called: list[str] = []

    def _fake_generate(snapshot_date: str, deck_slug: str, provider: str = "anthropic", model: str | None = None) -> None:
        called.append(f"{snapshot_date}:{deck_slug}:{provider}:{model}")

    monkeypatch.setattr(cli, "_generate_recommendation_report", _fake_generate)
    monkeypatch.setattr(
        sys,
        "argv",
        ["pokepocketpedia-generate-weekly-report", "--snapshot-date", snapshot],
    )
    exit_code = cli.generate_weekly_report()
    assert exit_code == 0
    assert called == []
    assert render_calls == [snapshot, snapshot]

    copied = tmp_path / "data" / "processed" / "reports" / snapshot / f"recommendation.{slug}.html"
    assert copied.exists()
    assert copied.read_text(encoding="utf-8") == "<html>old</html>"


def test_weekly_report_generates_missing_deck_reports_by_count(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    snapshot = "2026-02-09"
    _write_json(
        tmp_path / "data" / "processed" / "meta_metrics" / snapshot / "top_decks.json",
        {
            "items": [
                {"slug": "deck-low", "count": 30},
                {"slug": "deck-high", "count": 120},
                {"slug": "deck-mid", "count": 60},
            ]
        },
    )
    monkeypatch.setattr(
        cli,
        "render_meta_overview_report",
        lambda snapshot_date=None: (
            tmp_path
            / "data"
            / "processed"
            / "reports"
            / snapshot
            / "meta_overview.html"
        ),
    )
    called: list[str] = []

    def _fake_generate(snapshot_date: str, deck_slug: str, provider: str = "anthropic", model: str | None = None) -> None:
        called.append(f"{snapshot_date}:{deck_slug}:{provider}:{model}")

    monkeypatch.setattr(cli, "_generate_recommendation_report", _fake_generate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pokepocketpedia-generate-weekly-report",
            "--snapshot-date",
            snapshot,
            "--top-decks",
            "2",
        ],
    )
    exit_code = cli.generate_weekly_report()
    assert exit_code == 0
    assert called == [f"{snapshot}:deck-high:anthropic:None", f"{snapshot}:deck-mid:anthropic:None"]


def test_weekly_report_passes_provider_and_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    snapshot = "2026-02-09"
    _write_json(
        tmp_path / "data" / "processed" / "meta_metrics" / snapshot / "top_decks.json",
        {"items": [{"slug": "deck-a", "count": 99}]},
    )
    monkeypatch.setattr(
        cli,
        "render_meta_overview_report",
        lambda snapshot_date=None: (
            tmp_path
            / "data"
            / "processed"
            / "reports"
            / snapshot
            / "meta_overview.html"
        ),
    )

    seen: list[tuple[str, str, str, str | None]] = []

    def _fake_generate(snapshot_date: str, deck_slug: str, provider: str = "anthropic", model: str | None = None) -> None:
        seen.append((snapshot_date, deck_slug, provider, model))

    monkeypatch.setattr(cli, "_generate_recommendation_report", _fake_generate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pokepocketpedia-generate-weekly-report",
            "--snapshot-date",
            snapshot,
            "--provider",
            "openclaw",
            "--model",
            "openai-codex/gpt-5.3-codex",
        ],
    )

    exit_code = cli.generate_weekly_report()
    assert exit_code == 0
    assert seen == [(snapshot, "deck-a", "openclaw", "openai-codex/gpt-5.3-codex")]
