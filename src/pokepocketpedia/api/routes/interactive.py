from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/interactive", tags=["interactive"])


class DeckCardSelection(BaseModel):
    card_id: str = Field(min_length=1)
    count: int = Field(ge=1, le=2)


class EvaluateDeckRequest(BaseModel):
    snapshot_date: str | None = None
    cards: list[DeckCardSelection] = Field(default_factory=list)


class CompleteDeckRequest(BaseModel):
    snapshot_date: str | None = None
    cards: list[DeckCardSelection] = Field(default_factory=list)


@router.post("/evaluate-deck")
def evaluate_deck(request: EvaluateDeckRequest) -> dict[str, Any]:
    total_cards = sum(item.count for item in request.cards)
    if total_cards != 20:
        raise HTTPException(
            status_code=400,
            detail=f"Deck evaluation requires exactly 20 cards; received {total_cards}.",
        )

    return {
        "status": "phase_a_placeholder",
        "message": (
            "Phase A local foundation is ready. "
            "LLM deck evaluation logic will be implemented in Phase D."
        ),
        "total_cards": total_cards,
        "snapshot_date": request.snapshot_date,
    }


@router.post("/complete-deck")
def complete_deck(request: CompleteDeckRequest) -> dict[str, Any]:
    total_cards = sum(item.count for item in request.cards)
    if total_cards >= 20:
        raise HTTPException(
            status_code=400,
            detail=f"Deck completion requires fewer than 20 cards; received {total_cards}.",
        )

    return {
        "status": "phase_a_placeholder",
        "message": (
            "Phase A local foundation is ready. "
            "LLM deck completion logic will be implemented in Phase D."
        ),
        "selected_cards": total_cards,
        "remaining_slots": 20 - total_cards,
        "snapshot_date": request.snapshot_date,
    }
