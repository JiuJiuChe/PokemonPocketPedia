from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from pokepocketpedia.api.data_access import read_artifact, resolve_snapshot_date

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/top-decks")
def top_decks(
    snapshot_date: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        resolved_snapshot = resolve_snapshot_date("meta_metrics", snapshot_date)
        payload = read_artifact("meta_metrics", resolved_snapshot, "top_decks.json")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    items = payload.get("items", [])
    if not isinstance(items, list):
        raise HTTPException(status_code=500, detail="top_decks.json has invalid items payload.")

    total = len(items)
    page = [item for item in items if isinstance(item, dict)][offset : offset + limit]
    return {
        "snapshot_date": resolved_snapshot,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": page,
    }


@router.get("/top-cards")
def top_cards(
    snapshot_date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        resolved_snapshot = resolve_snapshot_date("meta_metrics", snapshot_date)
        payload = read_artifact("meta_metrics", resolved_snapshot, "top_cards.json")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    items = payload.get("items", [])
    if not isinstance(items, list):
        raise HTTPException(status_code=500, detail="top_cards.json has invalid items payload.")

    total = len(items)
    page = [item for item in items if isinstance(item, dict)][offset : offset + limit]
    return {
        "snapshot_date": resolved_snapshot,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": page,
    }


@router.get("/top-cards-by-archetype")
def top_cards_by_archetype(
    snapshot_date: str | None = Query(default=None),
    deck_slug: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        resolved_snapshot = resolve_snapshot_date("meta_metrics", snapshot_date)
        payload = read_artifact("meta_metrics", resolved_snapshot, "top_cards_by_archetype.json")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    items = payload.get("items", [])
    if not isinstance(items, list):
        raise HTTPException(
            status_code=500, detail="top_cards_by_archetype.json has invalid items payload."
        )

    filtered = [item for item in items if isinstance(item, dict)]
    if deck_slug:
        filtered = [
            item
            for item in filtered
            if str(item.get("deck_slug", "")).casefold() == deck_slug.casefold()
        ]

    total = len(filtered)
    page = filtered[offset : offset + limit]
    return {
        "snapshot_date": resolved_snapshot,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": page,
        "filters": {"deck_slug": deck_slug},
    }


@router.get("/trends")
def trends(snapshot_date: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        resolved_snapshot = resolve_snapshot_date("meta_metrics", snapshot_date)
        payload = read_artifact("meta_metrics", resolved_snapshot, "trends_1d_7d.json")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return payload


@router.get("/overview")
def overview(snapshot_date: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        resolved_snapshot = resolve_snapshot_date("meta_metrics", snapshot_date)
        payload = read_artifact("meta_metrics", resolved_snapshot, "overview.json")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return payload
