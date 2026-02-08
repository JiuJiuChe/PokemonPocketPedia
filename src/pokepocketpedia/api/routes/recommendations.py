from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from pokepocketpedia.api.data_access import read_artifact, resolve_snapshot_date

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/latest")
def latest_recommendations(
    snapshot_date: str | None = Query(default=None),
    top_n: int = Query(default=3, ge=1, le=10),
) -> dict[str, Any]:
    try:
        resolved_snapshot = resolve_snapshot_date("meta_metrics", snapshot_date)
        top_decks_payload = read_artifact("meta_metrics", resolved_snapshot, "top_decks.json")
        top_cards_payload = read_artifact("meta_metrics", resolved_snapshot, "top_cards.json")
        trends_payload = read_artifact("meta_metrics", resolved_snapshot, "trends_1d_7d.json")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    top_decks = [item for item in top_decks_payload.get("items", []) if isinstance(item, dict)]
    top_cards = [item for item in top_cards_payload.get("items", []) if isinstance(item, dict)]
    deck_trends = [item for item in trends_payload.get("decks", []) if isinstance(item, dict)]

    recommendations: list[dict[str, Any]] = []
    for deck in top_decks[:top_n]:
        slug = str(deck.get("slug", ""))
        trend = next((item for item in deck_trends if str(item.get("deck_slug")) == slug), None)
        recommendations.append(
            {
                "type": "deck_pick",
                "deck_slug": slug,
                "deck_name": deck.get("deck_name"),
                "reason": (
                    "Top meta share and stable trend."
                    if trend and trend.get("delta_share_pct_1d") is not None
                    else "Top meta share in current snapshot."
                ),
                "signals": {
                    "share_pct": deck.get("share_pct"),
                    "win_rate_pct": deck.get("win_rate_pct"),
                    "delta_share_pct_1d": trend.get("delta_share_pct_1d") if trend else None,
                    "delta_share_pct_7d": trend.get("delta_share_pct_7d") if trend else None,
                },
            }
        )

    tech_cards: list[dict[str, Any]] = []
    for card in top_cards[:top_n]:
        tech_cards.append(
            {
                "card_id": card.get("card_id"),
                "card_name": card.get("card_name"),
                "reason": "High weighted meta presence across top archetypes.",
                "signals": {
                    "weighted_share_points": card.get("weighted_share_points"),
                    "decks_seen": card.get("decks_seen"),
                    "avg_presence_rate": card.get("avg_presence_rate"),
                },
            }
        )

    notes = [
        "Rule-based recommendations for Phase 4 API baseline.",
        "Phase 5 will replace this with LLM reasoning constrained by these metrics artifacts.",
    ]

    return {
        "snapshot_date": resolved_snapshot,
        "top_n": top_n,
        "recommendations": recommendations,
        "tech_cards": tech_cards,
        "notes": notes,
    }
