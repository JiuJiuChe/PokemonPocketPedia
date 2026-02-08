from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from pokepocketpedia.api.data_access import read_artifact, resolve_snapshot_date

router = APIRouter(prefix="/decks", tags=["decks"])


@router.get("")
def list_decks(
    snapshot_date: str | None = Query(default=None),
    q: str | None = Query(default=None),
    slug: str | None = Query(default=None),
    min_share_pct: float | None = Query(default=None, ge=0.0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        resolved_snapshot = resolve_snapshot_date("decks", snapshot_date)
        payload = read_artifact("decks", resolved_snapshot, "decks.normalized.json")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    items = payload.get("items", [])
    if not isinstance(items, list):
        raise HTTPException(
            status_code=500,
            detail="decks.normalized.json has invalid items payload.",
        )

    filtered = [item for item in items if isinstance(item, dict)]
    if q:
        q_norm = q.casefold()
        filtered = [
            item
            for item in filtered
            if q_norm in str(item.get("deck_name", "")).casefold()
        ]
    if slug:
        filtered = [
            item
            for item in filtered
            if str(item.get("slug", "")).casefold() == slug.casefold()
        ]
    if min_share_pct is not None:
        filtered = [
            item
            for item in filtered
            if isinstance(item.get("share_pct"), (int, float))
            and float(item["share_pct"]) >= min_share_pct
        ]

    filtered.sort(
        key=lambda item: (
            -float(item["share_pct"]) if isinstance(item.get("share_pct"), (int, float)) else 0.0,
            -float(item["count"]) if isinstance(item.get("count"), (int, float)) else 0.0,
        )
    )

    total = len(filtered)
    page = filtered[offset : offset + limit]

    return {
        "snapshot_date": resolved_snapshot,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": page,
        "filters": {
            "q": q,
            "slug": slug,
            "min_share_pct": min_share_pct,
        },
    }
