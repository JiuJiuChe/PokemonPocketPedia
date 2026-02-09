"""Project CLI entry points used by local runs and GitHub Actions."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from pokepocketpedia.analyze.pipeline import run_analyze
from pokepocketpedia.ingest.pipeline import run_ingest
from pokepocketpedia.normalize.pipeline import run_normalize
from pokepocketpedia.recommend.context_builder import build_recommendation_context
from pokepocketpedia.recommend.llm_service import generate_recommendation
from pokepocketpedia.recommend.report_render import (
    render_recommendation_html,
    render_recommendation_markdown,
)
from pokepocketpedia.storage.files import write_json, write_text


def _todo(task_name: str) -> int:
    print(f"[TODO] {task_name} is scaffolded but not implemented yet.")
    return 0


def _date_from_env() -> date | None:
    # Optional override used by tests or backfills.
    from os import getenv

    raw = getenv("POKEPOCKETPEDIA_SNAPSHOT_DATE")
    if not raw:
        return None
    return date.fromisoformat(raw)


def _deck_detail_limit_from_env() -> int | None:
    from os import getenv

    raw = getenv("POKEPOCKETPEDIA_DECK_DETAIL_LIMIT")
    if raw is None or raw == "":
        return 100
    parsed = int(raw)
    if parsed <= 0:
        return None
    return parsed


def _decklist_samples_per_archetype_from_env() -> int:
    from os import getenv

    raw = getenv("POKEPOCKETPEDIA_DECKLIST_SAMPLES_PER_ARCHETYPE")
    if raw is None or raw == "":
        return 3
    parsed = int(raw)
    if parsed <= 0:
        return 1
    return parsed


def _recommend_deck_slug_from_env() -> str:
    from os import getenv

    raw = getenv("POKEPOCKETPEDIA_RECOMMEND_DECK_SLUG")
    if not raw:
        raise ValueError("Missing POKEPOCKETPEDIA_RECOMMEND_DECK_SLUG for recommend command.")
    return raw


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip())
    return cleaned or "deck"


def _recommend_output_paths(snapshot_date: str, deck_slug: str) -> dict[str, Path]:
    safe = _safe_slug(deck_slug)
    base_dir = Path("data/processed/reports") / snapshot_date
    return {
        "json": base_dir / f"recommendation.{safe}.json",
        "md": base_dir / f"recommendation.{safe}.md",
        "html": base_dir / f"recommendation.{safe}.html",
    }


def _load_recommendation_bundle(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def ingest() -> int:
    report = run_ingest(
        snapshot_date=_date_from_env(),
        deck_detail_limit=_deck_detail_limit_from_env(),
        decklist_samples_per_archetype=_decklist_samples_per_archetype_from_env(),
    )
    print(f"[ingest] status={report['status']} snapshot_date={report['snapshot_date']}")
    for source in report["sources"]:
        print(f"[ingest] {source['source']}: {source['status']}")
    return 0 if report["status"] == "success" else 1


def normalize() -> int:
    report = run_normalize(snapshot_date=_date_from_env())
    print(f"[normalize] status={report['status']} snapshot_date={report['snapshot_date']}")
    print(
        "[normalize] counts "
        f"cards={report['counts']['cards']} decks={report['counts']['decks']} "
        f"deck_cards={report['counts']['deck_cards']}"
    )
    if report["warnings"]:
        for warning in report["warnings"]:
            print(f"[normalize] warning: {warning}")
    if report.get("errors"):
        for error in report["errors"]:
            print(f"[normalize] error: {error}")
    return 1 if report["status"] == "error" else 0


def analyze() -> int:
    report = run_analyze(snapshot_date=_date_from_env())
    print(f"[analyze] status={report['status']} snapshot_date={report['snapshot_date']}")
    print(
        "[analyze] counts "
        f"top_decks={report['counts']['top_decks']} top_cards={report['counts']['top_cards']}"
    )
    if report["warnings"]:
        for warning in report["warnings"]:
            print(f"[analyze] warning: {warning}")
    return 0


def recommend() -> int:
    parser = argparse.ArgumentParser(prog="pokepocketpedia-recommend")
    parser.add_argument(
        "--format",
        choices=["json", "md", "html", "all"],
        default="all",
        help="Output artifacts to generate after LLM call.",
    )
    parser.add_argument(
        "--deck-slug",
        default=None,
        help="Deck slug override (otherwise uses POKEPOCKETPEDIA_RECOMMEND_DECK_SLUG).",
    )
    args = parser.parse_args(sys.argv[1:])

    try:
        snapshot = _date_from_env()
        deck_slug = args.deck_slug or _recommend_deck_slug_from_env()
        context_payload = build_recommendation_context(
            deck_slug=deck_slug,
            snapshot_date=snapshot.isoformat() if snapshot else None,
        )
        llm_result = generate_recommendation(
            llm_input=context_payload["llm_input"],
            provider="anthropic",
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"[recommend] error: {exc}")
        return 1

    print(
        f"[recommend] provider={llm_result['provider']} model={llm_result['model']} "
        f"snapshot_date={context_payload['snapshot_date']} deck_slug={context_payload['deck_slug']}"
    )
    paths = _recommend_output_paths(
        snapshot_date=str(context_payload["snapshot_date"]),
        deck_slug=str(context_payload["deck_slug"]),
    )
    bundle = {
        "snapshot_date": context_payload["snapshot_date"],
        "deck_slug": context_payload["deck_slug"],
        "context_payload": context_payload,
        "llm_result": llm_result,
    }
    write_json(paths["json"], bundle)
    print(f"[recommend] wrote json result: {paths['json']}")

    if args.format in {"md", "all"}:
        markdown = render_recommendation_markdown(
            context_payload=context_payload,
            llm_result=llm_result,
        )
        write_text(paths["md"], markdown)
        print(f"[recommend] wrote markdown report: {paths['md']}")

    if args.format in {"html", "all"}:
        html = render_recommendation_html(
            context_payload=context_payload,
            llm_result=llm_result,
        )
        write_text(paths["html"], html)
        print(f"[recommend] wrote html report: {paths['html']}")
    return 0


def render_recommendation_report() -> int:
    parser = argparse.ArgumentParser(prog="pokepocketpedia-render-recommendation")
    parser.add_argument("--input", required=True, help="Path to recommendation JSON bundle.")
    parser.add_argument(
        "--format",
        choices=["md", "html", "all"],
        default="all",
        help="Rendered output format.",
    )
    args = parser.parse_args(sys.argv[1:])

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[render-recommendation] error: input does not exist: {input_path}")
        return 1

    try:
        bundle = _load_recommendation_bundle(input_path)
        context_payload = bundle["context_payload"]
        llm_result = bundle["llm_result"]
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"[render-recommendation] error: invalid input bundle: {exc}")
        return 1

    snapshot_date = str(bundle.get("snapshot_date") or context_payload.get("snapshot_date"))
    deck_slug = str(bundle.get("deck_slug") or context_payload.get("deck_slug"))
    paths = _recommend_output_paths(snapshot_date=snapshot_date, deck_slug=deck_slug)

    if args.format in {"md", "all"}:
        markdown = render_recommendation_markdown(
            context_payload=context_payload,
            llm_result=llm_result,
        )
        write_text(paths["md"], markdown)
        print(f"[render-recommendation] wrote markdown report: {paths['md']}")

    if args.format in {"html", "all"}:
        html = render_recommendation_html(
            context_payload=context_payload,
            llm_result=llm_result,
        )
        write_text(paths["html"], html)
        print(f"[render-recommendation] wrote html report: {paths['html']}")

    return 0


def build_site() -> int:
    return _todo("build_site")


def run_daily() -> int:
    ingest_report = run_ingest(
        snapshot_date=_date_from_env(),
        deck_detail_limit=_deck_detail_limit_from_env(),
        decklist_samples_per_archetype=_decklist_samples_per_archetype_from_env(),
    )
    print(
        f"[daily] ingest status={ingest_report['status']} "
        f"snapshot_date={ingest_report['snapshot_date']}"
    )
    for source in ingest_report["sources"]:
        print(f"[daily] ingest {source['source']}: {source['status']}")
    if ingest_report["status"] != "success":
        return 1

    normalize_report = run_normalize(snapshot_date=_date_from_env())
    print(
        f"[daily] normalize status={normalize_report['status']} "
        f"snapshot_date={normalize_report['snapshot_date']}"
    )
    if normalize_report["status"] == "error":
        for error in normalize_report.get("errors", []):
            print(f"[daily] normalize error: {error}")
        return 1
    analyze_report = run_analyze(snapshot_date=_date_from_env())
    print(
        f"[daily] analyze status={analyze_report['status']} "
        f"snapshot_date={analyze_report['snapshot_date']}"
    )
    return 0
