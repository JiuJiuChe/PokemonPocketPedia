from fastapi import APIRouter

router = APIRouter(prefix="/decks", tags=["decks"])


@router.get("")
def list_decks() -> dict[str, list[dict[str, str]]]:
    return {"items": []}
