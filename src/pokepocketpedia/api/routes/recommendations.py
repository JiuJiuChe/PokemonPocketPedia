from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from pokepocketpedia.api.data_access import read_artifact, resolve_snapshot_date
from pokepocketpedia.recommend.context_builder import build_recommendation_context
from pokepocketpedia.recommend.llm_service import generate_recommendation

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class GenerateRecommendationRequest(BaseModel):
    deck_slug: str = Field(min_length=1)
    snapshot_date: str | None = None
    key_card_limit: int = Field(default=12, ge=3, le=40)
    provider: str = "anthropic"
    model: str | None = None


@router.get("/context")
def recommendation_context(
    deck_slug: str = Query(..., min_length=1),
    snapshot_date: str | None = Query(default=None),
    key_card_limit: int = Query(default=12, ge=3, le=40),
) -> dict[str, Any]:
    try:
        return build_recommendation_context(
            deck_slug=deck_slug,
            snapshot_date=snapshot_date,
            key_card_limit=key_card_limit,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generate")
def generate_recommendation_from_llm(request: GenerateRecommendationRequest) -> dict[str, Any]:
    try:
        context_payload = build_recommendation_context(
            deck_slug=request.deck_slug,
            snapshot_date=request.snapshot_date,
            key_card_limit=request.key_card_limit,
        )
        llm_result = generate_recommendation(
            llm_input=context_payload["llm_input"],
            provider=request.provider,
            model=request.model,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "snapshot_date": context_payload["snapshot_date"],
        "deck_slug": context_payload["deck_slug"],
        "provider": llm_result["provider"],
        "model": llm_result["model"],
        "generated_at": llm_result["generated_at"],
        "usage": llm_result["usage"],
        "output": llm_result["structured_output"],
        "debug": llm_result.get("debug"),
    }


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
