from fastapi import APIRouter

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("")
def list_cards() -> dict[str, list[dict[str, str]]]:
    return {"items": []}
