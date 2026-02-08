"""Runtime JSON Schema validation for generated artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_SCHEMA_FILES = {
    "cards.normalized": "cards.normalized.schema.json",
    "decks.normalized": "decks.normalized.schema.json",
    "deck_cards.normalized": "deck_cards.normalized.schema.json",
    "validation.report": "validation.report.schema.json",
    "meta_metrics.top_decks": "meta_metrics.list.schema.json",
    "meta_metrics.top_cards": "meta_metrics.list.schema.json",
    "meta_metrics.top_cards_by_archetype": "meta_metrics.list.schema.json",
    "meta_metrics.trends_1d_7d": "meta_metrics.trends.schema.json",
    "meta_metrics.overview": "meta_metrics.overview.schema.json",
}


def _schema_root() -> Path:
    return Path(__file__).resolve().parents[3] / "schemas" / "processed"


def _load_schema(schema_name: str) -> dict[str, Any]:
    if schema_name not in _SCHEMA_FILES:
        raise ValueError(f"Unknown schema name: {schema_name}")

    schema_path = _schema_root() / _SCHEMA_FILES[schema_name]
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Schema file does not contain a JSON object: {schema_path}")
    return payload


def validate_payload(payload: dict[str, Any], schema_name: str) -> None:
    schema = _load_schema(schema_name)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if not errors:
        return

    first = errors[0]
    location = "/".join(str(part) for part in first.absolute_path)
    if location:
        raise ValueError(
            f"Schema validation failed for {schema_name} at {location}: {first.message}"
        )
    raise ValueError(f"Schema validation failed for {schema_name}: {first.message}")
