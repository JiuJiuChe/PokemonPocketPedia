"""FastAPI application bootstrap."""

from fastapi import FastAPI

from pokepocketpedia.api.routes import cards, decks, metrics, recommendations

app = FastAPI(title="PokePocketPedia API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(cards.router)
app.include_router(decks.router)
app.include_router(metrics.router)
app.include_router(recommendations.router)
