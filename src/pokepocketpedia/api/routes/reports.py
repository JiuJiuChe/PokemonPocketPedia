from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from pokepocketpedia.api.data_access import processed_root

router = APIRouter(prefix="/reports", tags=["reports"])


def _latest_snapshot_dir(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing reports root: {path}")
    values: list[date] = []
    for child in path.iterdir():
        if not child.is_dir():
            continue
        try:
            values.append(date.fromisoformat(child.name))
        except ValueError:
            continue
    if not values:
        raise FileNotFoundError(f"No report snapshots found under {path}")
    return max(values).isoformat()


@router.get("/latest")
def latest_reports() -> dict[str, Any]:
    reports_root = Path(processed_root()) / "reports"
    try:
        snapshot = _latest_snapshot_dir(reports_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    snapshot_dir = reports_root / snapshot
    files = sorted(path.name for path in snapshot_dir.glob("*.html"))
    meta_overview = "meta_overview.html" if "meta_overview.html" in files else None
    deck_reports = [
        name
        for name in files
        if name.startswith("recommendation.") and name.endswith(".html")
    ]

    return {
        "snapshot_date": snapshot,
        "meta_overview": (
            f"/reports-static/{snapshot}/{meta_overview}" if meta_overview else None
        ),
        "deck_reports": [
            {
                "filename": name,
                "url": f"/reports-static/{snapshot}/{name}",
                "deck_slug": name.replace("recommendation.", "").replace(".html", ""),
            }
            for name in deck_reports
        ],
    }


@router.get("/snapshots")
def report_snapshots() -> dict[str, Any]:
    reports_root = Path(processed_root()) / "reports"
    if not reports_root.exists():
        raise HTTPException(status_code=404, detail=f"Missing reports root: {reports_root}")

    snapshots: list[dict[str, Any]] = []
    for snapshot_dir in _dated_dirs(reports_root):
        files = sorted(path.name for path in snapshot_dir.glob("*.html"))
        meta_name = "meta_overview.html" if "meta_overview.html" in files else None
        deck_reports = [
            name
            for name in files
            if name.startswith("recommendation.") and name.endswith(".html")
        ]
        snapshots.append(
            {
                "snapshot_date": snapshot_dir.name,
                "meta_overview": (
                    f"/reports-static/{snapshot_dir.name}/{meta_name}" if meta_name else None
                ),
                "deck_reports": [
                    {
                        "filename": name,
                        "url": f"/reports-static/{snapshot_dir.name}/{name}",
                        "deck_slug": name.replace("recommendation.", "").replace(".html", ""),
                    }
                    for name in deck_reports
                ],
            }
        )

    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail=f"No report snapshots found under {reports_root}",
        )

    return {
        "total": len(snapshots),
        "items": snapshots,
    }


def _dated_dirs(path: Path) -> list[Path]:
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
    return [path for _, path in dated]
