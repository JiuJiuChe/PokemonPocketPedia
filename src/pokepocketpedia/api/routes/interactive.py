from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from pokepocketpedia.api.data_access import read_artifact, resolve_snapshot_date
from pokepocketpedia.recommend.interactive_llm import (
    generate_interactive_analysis,
    generate_interactive_chat_reply,
)

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


class DeckTemplateCard(BaseModel):
    card_id: str
    card_name: str
    count: int = Field(ge=1, le=2)


class DeckTemplateResponse(BaseModel):
    snapshot_date: str
    deck_slug: str
    deck_name: str | None = None
    selected_cards: list[DeckTemplateCard] = Field(default_factory=list)
    total_cards: int = 0


class ChatTurnMessage(BaseModel):
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)


class ChatTurnRequest(BaseModel):
    snapshot_date: str | None = None
    mode: str = Field(default="evaluation")
    cards: list[DeckCardSelection] = Field(default_factory=list)
    history: list[ChatTurnMessage] = Field(default_factory=list)
    message: str = Field(min_length=1)


def _build_deck_template(
    deck_slug: str,
    snapshot_date: str | None = None,
) -> DeckTemplateResponse:
    try:
        snapshot = resolve_snapshot_date("decks", snapshot_date)
        decks_payload = read_artifact("decks", snapshot, "decks.normalized.json")
        deck_cards_payload = read_artifact("decks", snapshot, "deck_cards.normalized.json")
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    decks = [item for item in decks_payload.get("items", []) if isinstance(item, dict)]
    target = next(
        (
            item
            for item in decks
            if str(item.get("slug") or "").casefold() == deck_slug.casefold()
        ),
        None,
    )
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Deck slug '{deck_slug}' not found in snapshot {snapshot}.",
        )

    rows = [
        row
        for row in deck_cards_payload.get("items", [])
        if isinstance(row, dict)
        and str(row.get("deck_slug") or "").casefold() == deck_slug.casefold()
    ]
    rows.sort(
        key=lambda row: (
            -(float(row.get("presence_rate") or 0.0)),
            -(float(row.get("avg_count") or 0.0)),
            str(row.get("card_name") or ""),
        )
    )

    selected: list[DeckTemplateCard] = []
    total_cards = 0
    for row in rows:
        card_id = str(row.get("card_id") or "").strip()
        card_name = str(row.get("card_name") or "").strip()
        if not card_id or not card_name:
            continue
        avg_count = float(row.get("avg_count") or 0.0)
        proposed = 2 if avg_count >= 1.5 else 1
        if total_cards + proposed > 20:
            proposed = max(0, 20 - total_cards)
        if proposed <= 0:
            continue
        selected.append(
            DeckTemplateCard(
                card_id=card_id,
                card_name=card_name,
                count=min(2, proposed),
            )
        )
        total_cards += proposed
        if total_cards >= 20:
            break

    if total_cards < 20:
        for item in selected:
            if item.count >= 2:
                continue
            item.count += 1
            total_cards += 1
            if total_cards >= 20:
                break

    return DeckTemplateResponse(
        snapshot_date=snapshot,
        deck_slug=deck_slug,
        deck_name=(
            str(target.get("deck_name"))
            if target.get("deck_name") is not None
            else None
        ),
        selected_cards=selected,
        total_cards=total_cards,
    )


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


def _selected_card_details(
    cards: list[DeckCardSelection],
    snapshot_date: str | None,
) -> DeckCardDetailsResponse:
    if not cards:
        raise HTTPException(
            status_code=400,
            detail="At least one selected card is required.",
        )

    try:
        snapshot = resolve_snapshot_date("cards", snapshot_date)
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
    for card in cards:
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
        requested_count=len(cards),
        found_count=len(cards) - len(missing),
        missing_card_ids=missing,
        items=items,
    )


def _build_interactive_llm_input(
    mode: str,
    details: DeckCardDetailsResponse,
) -> dict[str, Any]:
    total_cards = sum(item.selected_count for item in details.items)
    pokemon_count = 0
    trainer_count = 0
    item_count = 0
    supporter_count = 0
    tool_count = 0
    stage_counts = {"Basic": 0, "Stage 1": 0, "Stage 2": 0, "Other": 0}
    pokemon_types: dict[str, int] = {}
    draw_search_cards: list[dict[str, Any]] = []

    selected_cards: list[dict[str, Any]] = []
    for item in details.items:
        selected_cards.append(
            {
                "card_id": item.resolved_card_id or item.requested_card_id,
                "card_name": item.name,
                "count": item.selected_count,
                "category": item.category,
                "trainer_type": item.trainer_type,
                "stage": item.stage,
                "hp": item.hp,
                "types": item.types,
                "ability_name": item.ability_name,
                "ability_text": item.ability_text,
                "effect": item.effect,
                "attacks": item.attacks,
                "usage": item.usage.model_dump() if item.usage else None,
            }
        )
        if not item.found:
            continue
        category = (item.category or "").casefold()
        if category == "pokemon":
            pokemon_count += item.selected_count
            stage = (item.stage or "").strip()
            if stage in stage_counts:
                stage_counts[stage] += item.selected_count
            else:
                stage_counts["Other"] += item.selected_count
            for one_type in item.types:
                key = str(one_type)
                pokemon_types[key] = pokemon_types.get(key, 0) + item.selected_count
        elif category == "trainer":
            trainer_count += item.selected_count
            trainer_type = (item.trainer_type or "").casefold()
            if trainer_type == "item":
                item_count += item.selected_count
            elif trainer_type == "supporter":
                supporter_count += item.selected_count
            elif trainer_type == "tool":
                tool_count += item.selected_count

        combined_text = (
            f"{item.name or ''} "
            f"{item.ability_text or ''} "
            f"{item.effect or ''}"
        ).casefold()
        if "draw" in combined_text or "search" in combined_text or "deck" in combined_text:
            draw_search_cards.append(
                {
                    "card_name": item.name,
                    "count": item.selected_count,
                    "hint": "text contains draw/search/deck keyword",
                }
            )

    top_decks_payload = read_artifact("meta_metrics", details.snapshot_date, "top_decks.json")
    top_cards_payload = read_artifact("meta_metrics", details.snapshot_date, "top_cards.json")
    top_decks = [item for item in top_decks_payload.get("items", []) if isinstance(item, dict)][:10]
    top_cards = [item for item in top_cards_payload.get("items", []) if isinstance(item, dict)][:10]
    top_deck_summary = [
        {
            "deck_slug": item.get("slug"),
            "deck_name": item.get("deck_name"),
            "count": item.get("count"),
            "win_rate_pct": item.get("win_rate_pct"),
            "share_pct": item.get("share_pct"),
        }
        for item in top_decks
    ]
    top_card_summary = [
        {
            "card_id": item.get("card_id"),
            "card_name": item.get("card_name"),
            "weighted_share_points": item.get("weighted_share_points"),
            "decks_seen": item.get("decks_seen"),
            "avg_presence_rate": item.get("avg_presence_rate"),
        }
        for item in top_cards
    ]

    selected_top_card_names = {
        str(item.get("card_name") or "").casefold() for item in selected_cards
    }
    replacement_candidates = [
        item
        for item in top_card_summary
        if str(item.get("card_name") or "").casefold() not in selected_top_card_names
    ][:25]

    return {
        "mode": mode,
        "task": (
            "For evaluation mode: evaluate this full 20-card deck. "
            "For completion mode: propose what is missing and how to finish to 20 cards."
        ),
        "required_reasoning": [
            (
                "Assess whether Pokemon/Item/Supporter portions are balanced and "
                "whether Basic/Stage 1/Stage 2 line is reasonable."
            ),
            (
                "Assess whether Pokemon type spread/energy typing assumptions are "
                "coherent for game plan."
            ),
            (
                "Assess consistency tools: draw power, search access, and key-card "
                "finding reliability."
            ),
            "Assess matchup outlook versus current top decks in the latest meta report.",
            (
                "Suggest better alternatives and identify opposing cards/decks this "
                "list struggles against."
            ),
        ],
        "output_requirements": [
            "executive_summary",
            "composition_assessment",
            "consistency_assessment",
            "meta_matchups",
            "alternatives_and_risks",
            "completion_plan",
            "recommended_additions",
            "confidence_and_limitations",
        ],
        "context": {
            "snapshot_date": details.snapshot_date,
            "selected_cards": selected_cards,
            "deck_totals": {
                "selected_total_cards": total_cards,
                "remaining_slots_to_20": max(0, 20 - total_cards),
                "pokemon_count": pokemon_count,
                "trainer_count": trainer_count,
                "item_count": item_count,
                "supporter_count": supporter_count,
                "tool_count": tool_count,
                "stage_counts": stage_counts,
                "pokemon_types": pokemon_types,
            },
            "consistency_signals": {
                "draw_or_search_cards": draw_search_cards,
            },
            "meta_context": {
                "top_decks": top_deck_summary,
                "top_cards": top_card_summary,
            },
            "replacement_candidates": replacement_candidates,
            "missing_card_ids": details.missing_card_ids,
        },
    }


@router.post("/evaluate-deck")
def evaluate_deck(request: EvaluateDeckRequest) -> dict[str, Any]:
    total_cards = sum(item.count for item in request.cards)
    if total_cards != 20:
        raise HTTPException(
            status_code=400,
            detail=f"Deck evaluation requires exactly 20 cards; received {total_cards}.",
        )
    details = _selected_card_details(request.cards, request.snapshot_date)
    llm_input = _build_interactive_llm_input("evaluation", details)
    try:
        llm_result = generate_interactive_analysis(llm_input=llm_input, mode="evaluation")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    output = llm_result["output"]
    return {
        "status": "ok",
        "mode": "evaluation",
        "message": output.get("executive_summary") or "Deck evaluation completed.",
        "snapshot_date": details.snapshot_date,
        "total_cards": total_cards,
        "usage": llm_result["usage"],
        "model": llm_result["model"],
        "output": output,
    }


@router.post("/complete-deck")
def complete_deck(request: CompleteDeckRequest) -> dict[str, Any]:
    total_cards = sum(item.count for item in request.cards)
    if total_cards >= 20:
        raise HTTPException(
            status_code=400,
            detail=f"Deck completion requires fewer than 20 cards; received {total_cards}.",
        )
    details = _selected_card_details(request.cards, request.snapshot_date)
    llm_input = _build_interactive_llm_input("completion", details)
    try:
        llm_result = generate_interactive_analysis(llm_input=llm_input, mode="completion")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    output = llm_result["output"]
    return {
        "status": "ok",
        "mode": "completion",
        "message": output.get("executive_summary") or "Deck completion analysis completed.",
        "snapshot_date": details.snapshot_date,
        "selected_cards": total_cards,
        "remaining_slots": 20 - total_cards,
        "usage": llm_result["usage"],
        "model": llm_result["model"],
        "output": output,
    }


@router.post("/chat-turn")
def chat_turn(request: ChatTurnRequest) -> dict[str, Any]:
    mode = request.mode.strip().casefold()
    if mode not in {"evaluation", "completion"}:
        raise HTTPException(
            status_code=400,
            detail="mode must be either 'evaluation' or 'completion'.",
        )
    total_cards = sum(item.count for item in request.cards)
    if total_cards <= 0:
        raise HTTPException(
            status_code=400,
            detail="At least one selected card is required.",
        )
    details = _selected_card_details(request.cards, request.snapshot_date)
    llm_input = _build_interactive_llm_input(mode, details)
    history = [
        {"role": item.role, "content": item.content}
        for item in request.history
        if item.role in {"assistant", "user"}
    ]
    try:
        llm_result = generate_interactive_chat_reply(
            context_input=llm_input,
            mode=mode,
            history=history,
            user_message=request.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "ok",
        "mode": mode,
        "snapshot_date": details.snapshot_date,
        "model": llm_result["model"],
        "usage": llm_result["usage"],
        "reply": llm_result["reply"],
    }


@router.get(
    "/deck-template",
    response_model=DeckTemplateResponse,
)
def deck_template(
    deck_slug: str = Query(..., min_length=1),
    snapshot_date: str | None = Query(default=None),
) -> DeckTemplateResponse:
    return _build_deck_template(deck_slug=deck_slug, snapshot_date=snapshot_date)


@router.post(
    "/deck-card-details",
    response_model=DeckCardDetailsResponse,
)
def deck_card_details(request: DeckCardDetailsRequest) -> DeckCardDetailsResponse:
    return _selected_card_details(request.cards, request.snapshot_date)
