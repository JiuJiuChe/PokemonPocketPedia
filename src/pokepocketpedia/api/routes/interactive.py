from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pokepocketpedia.api.data_access import read_artifact, resolve_snapshot_date

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


class DeckCardDetailsRequest(BaseModel):
    snapshot_date: str | None = None
    cards: list[DeckCardSelection] = Field(default_factory=list, max_length=40)


class CardUsageSummary(BaseModel):
    avg_presence_rate: float | None = None
    decks_seen: int | None = None
    weighted_share_points: float | None = None
    sample_decks_seen: int | None = None
    sample_max_presence_rate: float | None = None


class DeckCardDetailItem(BaseModel):
    requested_card_id: str
    resolved_card_id: str | None = None
    selected_count: int
    found: bool
    name: str | None = None
    set_id: str | None = None
    set_name: str | None = None
    category: str | None = None
    trainer_type: str | None = None
    stage: str | None = None
    hp: int | None = None
    types: list[str] = Field(default_factory=list)
    ability_name: str | None = None
    ability_text: str | None = None
    effect: str | None = None
    attacks: list[dict[str, Any]] = Field(default_factory=list)
    image: str | None = None
    usage: CardUsageSummary | None = None


class DeckCardDetailsResponse(BaseModel):
    snapshot_date: str
    requested_count: int
    found_count: int
    missing_card_ids: list[str] = Field(default_factory=list)
    items: list[DeckCardDetailItem] = Field(default_factory=list)


def _normalize_image_url(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    url = raw.strip()
    if not url:
        return None
    lowered = url.casefold()
    if lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return url
    if "assets.tcgdex.net" not in lowered:
        return url
    if lowered.endswith("/high") or lowered.endswith("/low"):
        return f"{url}.webp"
    return f"{url}/high.webp"


def _canonical_card_id(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    parts = text.split("-")
    if len(parts) >= 2:
        prefix = "-".join(parts[:-1]).upper()
        suffix_raw = parts[-1].lstrip("0")
        suffix = suffix_raw if suffix_raw else "0"
        return f"{prefix}-{suffix}".casefold()
    return text.casefold()


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


@router.post(
    "/deck-card-details",
    response_model=DeckCardDetailsResponse,
)
def deck_card_details(request: DeckCardDetailsRequest) -> DeckCardDetailsResponse:
    if not request.cards:
        raise HTTPException(
            status_code=400,
            detail="At least one selected card is required.",
        )

    try:
        snapshot = resolve_snapshot_date("cards", request.snapshot_date)
        cards_payload = read_artifact("cards", snapshot, "cards.normalized.json")
        top_cards_payload = read_artifact("meta_metrics", snapshot, "top_cards.json")
        deck_cards_payload = read_artifact("decks", snapshot, "deck_cards.normalized.json")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    cards_items = cards_payload.get("items", [])
    top_cards_items = top_cards_payload.get("items", [])
    deck_cards_items = deck_cards_payload.get("items", [])
    if not isinstance(cards_items, list):
        raise HTTPException(status_code=500, detail="cards.normalized.json has invalid items.")
    if not isinstance(top_cards_items, list):
        raise HTTPException(status_code=500, detail="top_cards.json has invalid items.")
    if not isinstance(deck_cards_items, list):
        raise HTTPException(
            status_code=500,
            detail="deck_cards.normalized.json has invalid items.",
        )

    cards_lookup: dict[str, dict[str, Any]] = {}
    for item in cards_items:
        if not isinstance(item, dict):
            continue
        card_id = item.get("card_id")
        key = _canonical_card_id(card_id)
        if key and key not in cards_lookup:
            cards_lookup[key] = item

    top_cards_lookup: dict[str, dict[str, Any]] = {}
    top_cards_by_name: dict[str, dict[str, Any]] = {}
    for item in top_cards_items:
        if not isinstance(item, dict):
            continue
        key = _canonical_card_id(item.get("card_id"))
        if key and key not in top_cards_lookup:
            top_cards_lookup[key] = item
        name = str(item.get("card_name") or "").strip().casefold()
        if name and name not in top_cards_by_name:
            top_cards_by_name[name] = item

    sample_usage: dict[str, dict[str, Any]] = {}
    for row in deck_cards_items:
        if not isinstance(row, dict):
            continue
        key = _canonical_card_id(row.get("card_id"))
        if not key:
            continue
        hit = sample_usage.setdefault(
            key,
            {"deck_slugs": set(), "max_presence_rate": None},
        )
        deck_slug = str(row.get("deck_slug") or "").strip()
        if deck_slug:
            hit["deck_slugs"].add(deck_slug)
        presence_raw = row.get("presence_rate")
        if isinstance(presence_raw, (int, float)):
            current = float(presence_raw)
            previous = hit["max_presence_rate"]
            hit["max_presence_rate"] = (
                current if previous is None else max(float(previous), current)
            )

    items: list[DeckCardDetailItem] = []
    missing: list[str] = []
    for card in request.cards:
        key = _canonical_card_id(card.card_id)
        card_doc = cards_lookup.get(key)
        if not card_doc:
            missing.append(card.card_id)
            items.append(
                DeckCardDetailItem(
                    requested_card_id=card.card_id,
                    selected_count=card.count,
                    found=False,
                )
            )
            continue

        resolved_id = str(card_doc.get("card_id") or "")
        name = str(card_doc.get("name") or "")
        top_hit = top_cards_lookup.get(key) or top_cards_by_name.get(name.casefold())
        sample_hit = sample_usage.get(key)
        sample_decks_seen = (
            len(sample_hit["deck_slugs"])
            if sample_hit and isinstance(sample_hit.get("deck_slugs"), set)
            else None
        )
        sample_max_presence_rate = (
            float(sample_hit["max_presence_rate"])
            if sample_hit and isinstance(sample_hit.get("max_presence_rate"), (int, float))
            else None
        )
        usage = CardUsageSummary(
            avg_presence_rate=(
                float(top_hit["avg_presence_rate"])
                if top_hit and isinstance(top_hit.get("avg_presence_rate"), (int, float))
                else None
            ),
            decks_seen=(
                int(top_hit["decks_seen"])
                if top_hit and isinstance(top_hit.get("decks_seen"), (int, float))
                else None
            ),
            weighted_share_points=(
                float(top_hit["weighted_share_points"])
                if top_hit and isinstance(top_hit.get("weighted_share_points"), (int, float))
                else None
            ),
            sample_decks_seen=sample_decks_seen,
            sample_max_presence_rate=sample_max_presence_rate,
        )

        items.append(
            DeckCardDetailItem(
                requested_card_id=card.card_id,
                resolved_card_id=resolved_id or None,
                selected_count=card.count,
                found=True,
                name=name or None,
                set_id=(
                    str(card_doc.get("set_id"))
                    if card_doc.get("set_id") is not None
                    else None
                ),
                set_name=(
                    str(card_doc.get("set_name"))
                    if card_doc.get("set_name") is not None
                    else None
                ),
                category=(
                    str(card_doc.get("category"))
                    if card_doc.get("category") is not None
                    else None
                ),
                trainer_type=(
                    str(card_doc.get("trainer_type"))
                    if card_doc.get("trainer_type") is not None
                    else None
                ),
                stage=str(card_doc.get("stage")) if card_doc.get("stage") is not None else None,
                hp=int(card_doc["hp"]) if isinstance(card_doc.get("hp"), int) else None,
                types=[
                    str(item)
                    for item in card_doc.get("types", [])
                    if isinstance(item, str)
                ]
                if isinstance(card_doc.get("types"), list)
                else [],
                ability_name=(
                    str(card_doc.get("ability_name"))
                    if card_doc.get("ability_name") is not None
                    else None
                ),
                ability_text=(
                    str(card_doc.get("ability_text"))
                    if card_doc.get("ability_text") is not None
                    else None
                ),
                effect=str(card_doc.get("effect")) if card_doc.get("effect") is not None else None,
                attacks=(
                    [item for item in card_doc.get("attacks", []) if isinstance(item, dict)]
                    if isinstance(card_doc.get("attacks"), list)
                    else []
                ),
                image=_normalize_image_url(card_doc.get("image")),
                usage=usage,
            )
        )

    return DeckCardDetailsResponse(
        snapshot_date=snapshot,
        requested_count=len(request.cards),
        found_count=len(request.cards) - len(missing),
        missing_card_ids=missing,
        items=items,
    )
