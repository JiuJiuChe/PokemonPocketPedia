from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from pokepocketpedia.api.data_access import read_artifact, resolve_snapshot_date

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("")
def list_cards(
    snapshot_date: str | None = Query(default=None),
    q: str | None = Query(default=None),
    set_id: str | None = Query(default=None),
    card_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        resolved_snapshot = resolve_snapshot_date("cards", snapshot_date)
        payload = read_artifact("cards", resolved_snapshot, "cards.normalized.json")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    items = payload.get("items", [])
    if not isinstance(items, list):
        raise HTTPException(
            status_code=500,
            detail="cards.normalized.json has invalid items payload.",
        )

    filtered = [item for item in items if isinstance(item, dict)]
    if q:
        q_norm = q.casefold()
        filtered = [
            item
            for item in filtered
            if q_norm in str(item.get("name", "")).casefold()
            or q_norm in str(item.get("ability_text", "")).casefold()
            or q_norm in str(item.get("effect", "")).casefold()
        ]
    if set_id:
        filtered = [
            item
            for item in filtered
            if str(item.get("set_id", "")).casefold() == set_id.casefold()
        ]
    if card_id:
        filtered = [
            item
            for item in filtered
            if str(item.get("card_id", "")).casefold() == card_id.casefold()
        ]

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
            "set_id": set_id,
            "card_id": card_id,
        },
    }
