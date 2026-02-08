"""Helpers to read processed artifacts for API routes."""

from __future__ import annotations

import json
from datetime import date
from os import getenv
from pathlib import Path
from typing import Any


def processed_root() -> Path:
    raw = getenv("POKEPOCKETPEDIA_PROCESSED_ROOT")
    if raw:
        return Path(raw)
    return Path("data/processed")


def _iso_dates_under(path: Path) -> list[str]:
    if not path.exists():
        return []

    snapshots: list[date] = []
    for child in path.iterdir():
        if not child.is_dir():
            continue
        try:
            snapshots.append(date.fromisoformat(child.name))
        except ValueError:
            continue
    return [item.isoformat() for item in sorted(snapshots)]


def resolve_snapshot_date(section: str, requested: str | None) -> str:
    section_dir = processed_root() / section
    available = _iso_dates_under(section_dir)
    if not available:
        raise FileNotFoundError(f"No snapshots found for section '{section}' in {section_dir}")

    if requested is None:
        return available[-1]

    if requested not in available:
        raise FileNotFoundError(
            f"Snapshot '{requested}' not found for section '{section}'. "
            f"Available latest snapshot: {available[-1]}"
        )
    return requested


def read_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def read_artifact(section: str, snapshot_date: str, filename: str) -> dict[str, Any]:
    path = processed_root() / section / snapshot_date / filename
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found: {path}")
    return read_json_file(path)

