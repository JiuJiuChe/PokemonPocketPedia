"""Project CLI entry points used by local runs and GitHub Actions."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any

from pokepocketpedia.analyze.pipeline import run_analyze
from pokepocketpedia.ingest.pipeline import run_ingest
from pokepocketpedia.normalize.pipeline import run_normalize
from pokepocketpedia.recommend.context_builder import build_recommendation_context
from pokepocketpedia.common.providers import model_from_env
from pokepocketpedia.recommend.llm_service import generate_recommendation
from pokepocketpedia.recommend.report_render import (
    render_recommendation_html,
    render_recommendation_markdown,
)
from pokepocketpedia.report.meta_overview import render_meta_overview_report
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

def _recommend_provider_from_env() -> str:
    from os import getenv

    return str(getenv("POKEPOCKETPEDIA_RECOMMEND_PROVIDER", "anthropic") or "anthropic").strip()


def _recommend_model_from_env(provider: str) -> str | None:
    from os import getenv

    if provider == "openclaw":
        value = str(getenv("POKEPOCKETPEDIA_OPENCLAW_MODEL", "") or "").strip()
        return value or None
    value = str(getenv("POKEPOCKETPEDIA_ANTHROPIC_MODEL", "") or "").strip()
    return value or None



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


def _latest_snapshot_dir(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing metrics root: {path}")
    values: list[date] = []
    for child in path.iterdir():
        if not child.is_dir():
            continue
        try:
            values.append(date.fromisoformat(child.name))
        except ValueError:
            continue
    if not values:
        raise FileNotFoundError(f"No snapshot directories found under {path}")
    return max(values).isoformat()


def _deck_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned.isdigit():
            return int(cleaned)
    return 0


def _top_deck_slugs_by_count(snapshot_date: str, limit: int = 10) -> list[str]:
    path = Path("data/processed/meta_metrics") / snapshot_date / "top_decks.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return []
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    items.sort(key=lambda item: -_deck_count(item.get("count")))
    slugs: list[str] = []
    for item in items:
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        if slug in slugs:
            continue
        slugs.append(slug)
        if len(slugs) >= limit:
            break
    return slugs


def _dated_dirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    dated: list[tuple[date, Path]] = []
    for child in path.iterdir():
        if not child.is_dir():
            continue
        try:
            parsed = date.fromisoformat(child.name)
        except ValueError:
            continue
        dated.append((parsed, child))
    dated.sort(key=lambda pair: pair[0], reverse=True)
    return [child for _, child in dated]


def _latest_report_snapshot(reports_root: Path) -> str:
    candidates = _dated_dirs(reports_root)
    if not candidates:
        raise FileNotFoundError(f"No report snapshots found under {reports_root}")
    return candidates[0].name


def _copy_html_reports(snapshot_dir: Path, site_reports_dir: Path) -> list[Path]:
    copied: list[Path] = []
    for source in sorted(snapshot_dir.glob("*.html")):
        target = site_reports_dir / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def _build_site_index(
    snapshot_date: str,
    meta_filename: str | None,
    deck_report_filenames: list[str],
) -> str:
    meta_link = (
        f'<p><a href="reports/{snapshot_date}/{meta_filename}">Open meta overview</a></p>'
        if meta_filename
        else "<p>Meta overview report was not found for this snapshot.</p>"
    )
    deck_items = "".join(
        (
            f'<li><a href="reports/{snapshot_date}/{name}">'
            f"{name.replace('recommendation.', '').replace('.html', '')}</a></li>"
        )
        for name in deck_report_filenames
    )
    if not deck_items:
        deck_items = "<li>No deck recommendation HTML files found.</li>"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "  <title>PokePocketPedia Reports</title>\n"
        "  <style>\n"
        "    body {\n"
        "      margin: 0;\n"
        "      font-family: 'Trebuchet MS', 'Gill Sans', sans-serif;\n"
        "      background: #f7f3e8;\n"
        "      color: #1f2a30;\n"
        "    }\n"
        "    main { max-width: 900px; margin: 0 auto; padding: 2rem 1rem 3rem; }\n"
        "    .panel {\n"
        "      background: #fff;\n"
        "      border: 1px solid #ddd3bd;\n"
        "      border-radius: 12px;\n"
        "      padding: 1rem;\n"
        "    }\n"
        "    h1 { margin: 0 0 .3rem; }\n"
        "    a { color: #0f3c89; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        "    <h1>PokePocketPedia Reports</h1>\n"
        f"    <p>Snapshot: {snapshot_date}</p>\n"
        '    <section class="panel">\n'
        "      <h2>Meta Overview</h2>\n"
        f"      {meta_link}\n"
        "      <h2>Deck Reports</h2>\n"
        f"      <ul>{deck_items}</ul>\n"
        "    </section>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def _reuse_existing_recommendation(
    snapshot_date: str,
    deck_slug: str,
) -> bool:
    reports_root = Path("data/processed/reports")
    target_dir = reports_root / snapshot_date
    safe_slug = _safe_slug(deck_slug)
    html_name = f"recommendation.{safe_slug}.html"
    md_name = f"recommendation.{safe_slug}.md"
    json_name = f"recommendation.{safe_slug}.json"

    current_html = target_dir / html_name
    if current_html.exists():
        return True

    for snapshot_dir in _dated_dirs(reports_root):
        if snapshot_dir.name == snapshot_date:
            continue
        source_html = snapshot_dir / html_name
        if not source_html.exists():
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_html, target_dir / html_name)
        source_md = snapshot_dir / md_name
        if source_md.exists():
            shutil.copy2(source_md, target_dir / md_name)
        source_json = snapshot_dir / json_name
        if source_json.exists():
            shutil.copy2(source_json, target_dir / json_name)
        print(f"[weekly-report] reused {deck_slug} from snapshot {snapshot_dir.name}")
        return True
    return False


def _generate_recommendation_report(snapshot_date: str, deck_slug: str) -> None:
    context_payload = build_recommendation_context(
        deck_slug=deck_slug,
        snapshot_date=snapshot_date,
    )
    llm_result = generate_recommendation(
        llm_input=context_payload["llm_input"],
        provider="anthropic",
    )
    paths = _recommend_output_paths(snapshot_date=snapshot_date, deck_slug=deck_slug)
    bundle = {
        "snapshot_date": context_payload["snapshot_date"],
        "deck_slug": context_payload["deck_slug"],
        "context_payload": context_payload,
        "llm_result": llm_result,
    }
    write_json(paths["json"], bundle)
    markdown = render_recommendation_markdown(
        context_payload=context_payload,
        llm_result=llm_result,
    )
    write_text(paths["md"], markdown)
    html = render_recommendation_html(
        context_payload=context_payload,
        llm_result=llm_result,
    )
    write_text(paths["html"], html)


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
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openclaw"],
        default=_recommend_provider_from_env(),
        help="LLM provider for recommendation generation.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model override for selected provider (falls back to provider env var).",
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
            provider=args.provider,
            model=args.model or _recommend_model_from_env(args.provider),
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


def render_meta_report() -> int:
    parser = argparse.ArgumentParser(prog="pokepocketpedia-render-meta-report")
    parser.add_argument(
        "--snapshot-date",
        default=None,
        help="Snapshot date YYYY-MM-DD (defaults to latest available in meta_metrics).",
    )
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "openclaw"],
        help="Summary provider for meta overview.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional provider-specific model override.",
    )
    args = parser.parse_args(sys.argv[1:])

    snapshot_override = args.snapshot_date
    if snapshot_override is None:
        date_env = _date_from_env()
        snapshot_override = date_env.isoformat() if date_env else None

    try:
        output_path = render_meta_overview_report(
            snapshot_date=snapshot_override,
            summary_provider=args.provider,
            summary_model=args.model,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"[render-meta-report] error: {exc}")
        return 1

    print(f"[render-meta-report] wrote report: {output_path}")
    return 0


def generate_weekly_report() -> int:
    parser = argparse.ArgumentParser(prog="pokepocketpedia-generate-weekly-report")
    parser.add_argument(
        "--snapshot-date",
        default=None,
        help="Snapshot date YYYY-MM-DD (defaults to latest available in meta_metrics).",
    )
    parser.add_argument(
        "--top-decks",
        type=int,
        default=10,
        help="Number of top decks to ensure recommendation reports for.",
    )
    args = parser.parse_args(sys.argv[1:])

    snapshot_override = args.snapshot_date
    if snapshot_override is None:
        date_env = _date_from_env()
        snapshot_override = date_env.isoformat() if date_env else None

    try:
        snapshot_date = (
            snapshot_override
            if snapshot_override is not None
            else _latest_snapshot_dir(Path("data/processed/meta_metrics"))
        )
        output_path = render_meta_overview_report(snapshot_date=snapshot_date)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[weekly-report] error while rendering meta overview: {exc}")
        return 1

    print(f"[weekly-report] wrote meta overview: {output_path}")
    try:
        top_slugs = _top_deck_slugs_by_count(
            snapshot_date=snapshot_date,
            limit=max(args.top_decks, 1),
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"[weekly-report] error loading top decks: {exc}")
        return 1
    if not top_slugs:
        print(f"[weekly-report] no deck slugs found for snapshot {snapshot_date}")
        return 1

    generated = 0
    reused = 0
    failed = 0
    for slug in top_slugs:
        if _reuse_existing_recommendation(snapshot_date=snapshot_date, deck_slug=slug):
            reused += 1
            continue
        try:
            _generate_recommendation_report(snapshot_date=snapshot_date, deck_slug=slug)
            print(f"[weekly-report] generated recommendation report for {slug}")
            generated += 1
        except (FileNotFoundError, ValueError) as exc:
            print(f"[weekly-report] failed to generate report for {slug}: {exc}")
            failed += 1

    try:
        refreshed_path = render_meta_overview_report(snapshot_date=snapshot_date)
        print(f"[weekly-report] refreshed meta overview links: {refreshed_path}")
    except (FileNotFoundError, ValueError) as exc:
        print(f"[weekly-report] failed to refresh meta overview: {exc}")
        failed += 1

    print(
        f"[weekly-report] done snapshot={snapshot_date} "
        f"generated={generated} reused={reused} failed={failed}"
    )
    return 1 if failed > 0 else 0


def build_site() -> int:
    parser = argparse.ArgumentParser(prog="pokepocketpedia-build-site")
    parser.add_argument(
        "--snapshot-date",
        default=None,
        help="Snapshot date YYYY-MM-DD (defaults to latest under data/processed/reports).",
    )
    parser.add_argument(
        "--reports-root",
        default="data/processed/reports",
        help="Source reports root directory.",
    )
    parser.add_argument(
        "--docs-root",
        default="docs",
        help="Destination static site directory for GitHub Pages.",
    )
    args = parser.parse_args(sys.argv[1:])

    reports_root = Path(args.reports_root)
    docs_root = Path(args.docs_root)
    snapshot_date = args.snapshot_date or _date_from_env()
    if isinstance(snapshot_date, date):
        snapshot_date = snapshot_date.isoformat()
    if snapshot_date is None:
        try:
            snapshot_date = _latest_report_snapshot(reports_root)
        except FileNotFoundError as exc:
            print(f"[build-site] error: {exc}")
            return 1

    source_snapshot_dir = reports_root / snapshot_date
    if not source_snapshot_dir.exists():
        print(f"[build-site] error: snapshot not found: {source_snapshot_dir}")
        return 1

    site_snapshot_dir = docs_root / "reports" / snapshot_date
    copied = _copy_html_reports(source_snapshot_dir, site_snapshot_dir)
    if not copied:
        print(f"[build-site] error: no HTML reports found in {source_snapshot_dir}")
        return 1

    copied_names = [path.name for path in copied]
    meta_filename = "meta_overview.html" if "meta_overview.html" in copied_names else None
    deck_filenames = sorted(
        [
            name
            for name in copied_names
            if name.startswith("recommendation.") and name.endswith(".html")
        ]
    )
    index_html = _build_site_index(
        snapshot_date,
        meta_filename,
        deck_filenames,
    )
    write_text(docs_root / "index.html", index_html)
    write_text(docs_root / ".nojekyll", "")

    print(
        f"[build-site] wrote site index: {docs_root / 'index.html'} | "
        f"copied_html_files={len(copied)} snapshot={snapshot_date}"
    )
    return 0


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
