"""FastAPI application bootstrap."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pokepocketpedia.api.routes import cards, decks, interactive, metrics, recommendations, reports

app = FastAPI(title="PokePocketPedia API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(cards.router)
app.include_router(decks.router)
app.include_router(metrics.router)
app.include_router(recommendations.router)
app.include_router(reports.router)
app.include_router(interactive.router)

app.mount(
    "/reports-static",
    StaticFiles(directory=Path("data/processed/reports"), check_dir=False),
    name="reports_static",
)
