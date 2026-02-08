# PokePocketPedia

Data pipeline and dashboard project for Pokemon TCG Pocket meta analysis.

## Prerequisites
- Python 3.11+
- `uv` installed

## Setup

```bash
uv sync --extra dev
```

## Run API (scaffold)

```bash
uv run uvicorn pokepocketpedia.api.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Phase 1: Pull cards and deck info

Run ingestion for today:

```bash
uv run pokepocketpedia-ingest
```

During ingest, a terminal progress bar is shown for:
- Pocket sets fetch
- Pocket card detail fetch
- Deck page fetch/parse/write

Run ingestion for a specific snapshot date:

```bash
POKEPOCKETPEDIA_SNAPSHOT_DATE=2026-02-08 uv run pokepocketpedia-ingest
```

Daily pipeline entry point (currently same as ingest):

```bash
uv run pokepocketpedia-run-daily
```

## Output files

After ingestion, files are written to:

- `data/raw/cards/YYYY-MM-DD/cards.json`
- `data/raw/decks/YYYY-MM-DD/decks.json`
- `data/raw/decks/YYYY-MM-DD/decks_page.html`
- `data/raw/runs/YYYY-MM-DD/ingest_run.json`

### `cards.json` structure
- `series_payload`: Pocket series metadata
- `sets`: set payloads
- `cards`: full card objects (card-level fields from TCGdex)
- `stats`: `set_count`, `card_count`

### `decks.json` structure
- `overview`: selected game/format/set and summary counts
- `decks`: parsed deck rows from Limitless table
  - includes rank, deck name, deck URL, matchup URL, count, share, win rate, icons
- `stats`: `deck_count`

### `ingest_run.json` structure
- overall run status
- per-source status (`cards`, `decks`)
- source URLs
- timestamps

## Manual validation checklist

1. Verify files exist for your date under `data/raw/`.
2. Open `data/raw/runs/YYYY-MM-DD/ingest_run.json` and confirm `status` is `success` or inspect source-level errors.
3. In `cards.json`, confirm:
   - `stats.card_count > 0`
   - `cards[0]` has expected fields like `id`, `name` (and often `hp`, `attacks`, `abilities`).
4. In `decks.json`, confirm:
   - `stats.deck_count > 0`
   - `decks[0]` has `deck_name`, `count`, `share_pct`, `win_rate_pct`.

## Test and lint

```bash
uv run ruff check .
uv run pytest
```

## GitHub Actions

Workflows:
- `.github/workflows/ci.yml`: lint + test on push/PR
- `.github/workflows/daily-update.yml`: scheduled/manual daily pipeline run

Current daily workflow behavior:
- installs deps with `uv`
- runs `pokepocketpedia-run-daily`

## Current scope status
- Phase 0: complete
- Phase 1 ingestion MVP: complete
- Phase 2 normalization and analytics: pending

See `project_plan.md` for roadmap and status.
