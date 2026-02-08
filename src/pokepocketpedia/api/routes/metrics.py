from fastapi import APIRouter

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/top-decks")
def top_decks() -> dict[str, list[dict[str, str]]]:
    return {"items": []}


@router.get("/top-cards")
def top_cards() -> dict[str, list[dict[str, str]]]:
    return {"items": []}
