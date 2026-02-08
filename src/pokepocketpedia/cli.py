"""Project CLI entry points used by local runs and GitHub Actions."""

from __future__ import annotations

from datetime import date

from pokepocketpedia.ingest.pipeline import run_ingest


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


def ingest() -> int:
    report = run_ingest(snapshot_date=_date_from_env())
    print(f"[ingest] status={report['status']} snapshot_date={report['snapshot_date']}")
    for source in report["sources"]:
        print(f"[ingest] {source['source']}: {source['status']}")
    return 0 if report["status"] == "success" else 1


def normalize() -> int:
    return _todo("normalize")


def analyze() -> int:
    return _todo("analyze")


def recommend() -> int:
    return _todo("recommend")


def build_site() -> int:
    return _todo("build_site")


def run_daily() -> int:
    # Phase 1 daily run currently maps to ingestion only.
    return ingest()
