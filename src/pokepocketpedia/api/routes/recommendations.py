from fastapi import APIRouter

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/latest")
def latest_recommendations() -> dict[str, str]:
    return {"message": "Recommendations pipeline not implemented yet."}
