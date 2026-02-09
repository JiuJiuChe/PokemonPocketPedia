# PokePocketPedia

Data pipeline and dashboard project for Pokemon TCG Pocket meta analysis.

## Prerequisites
- Python 3.11+
- `uv` installed

## Setup

```bash
uv sync --extra dev
```

## Run API

```bash
uv run uvicorn pokepocketpedia.api.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Recommendation endpoints:

```bash
# Build LLM-ready context for a specific deck
curl "http://127.0.0.1:8000/recommendations/context?deck_slug=hydreigon-mega-absol-ex-b1"

# Generate deck strategy using Anthropic (requires ANTHROPIC_API_KEY)
curl -X POST "http://127.0.0.1:8000/recommendations/generate" \
  -H "Content-Type: application/json" \
  -d '{"deck_slug":"hydreigon-mega-absol-ex-b1","provider":"anthropic","model":"claude-sonnet-4-5-20250929"}'
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
- Deck detail crawl (archetype page -> sample tournament decklist)

Deck detail crawl limit (default: 100 decks by rank):

```bash
POKEPOCKETPEDIA_DECK_DETAIL_LIMIT=200 uv run pokepocketpedia-ingest
```

Set `POKEPOCKETPEDIA_DECK_DETAIL_LIMIT=0` (or any `<=0`) to crawl all decks.

Decklist samples per archetype (default: 3):

```bash
POKEPOCKETPEDIA_DECKLIST_SAMPLES_PER_ARCHETYPE=5 uv run pokepocketpedia-ingest
```

Run ingestion for a specific snapshot date:

```bash
POKEPOCKETPEDIA_SNAPSHOT_DATE=2026-02-08 uv run pokepocketpedia-ingest
```

Daily pipeline entry point (ingest + normalize + analyze):

```bash
uv run pokepocketpedia-run-daily
```

LLM recommendation CLI:

```bash
ANTHROPIC_API_KEY=... \
POKEPOCKETPEDIA_RECOMMEND_DECK_SLUG=hydreigon-mega-absol-ex-b1 \
uv run pokepocketpedia-recommend
```

Decoupled generation vs rendering:

```bash
# 1) Call LLM and save JSON only (no markdown/html rendering)
ANTHROPIC_API_KEY=... \
POKEPOCKETPEDIA_RECOMMEND_DECK_SLUG=hydreigon-mega-absol-ex-b1 \
uv run pokepocketpedia-recommend --format json

# 2) Render markdown/html later from saved JSON without calling LLM
uv run pokepocketpedia-render-recommendation \
  --input data/processed/reports/YYYY-MM-DD/recommendation.hydreigon-mega-absol-ex-b1.json \
  --format all
```

Optional env vars:
- `POKEPOCKETPEDIA_ANTHROPIC_MODEL` (default: `claude-sonnet-4-5-20250929`)
- `POKEPOCKETPEDIA_SNAPSHOT_DATE` (use a specific snapshot for recommendation)

Generated report files:
- `data/processed/reports/YYYY-MM-DD/recommendation.<deck_slug>.json`
- `data/processed/reports/YYYY-MM-DD/recommendation.<deck_slug>.md`
- `data/processed/reports/YYYY-MM-DD/recommendation.<deck_slug>.html`

Meta overview report (no LLM):

```bash
uv run pokepocketpedia-render-meta-report
# optional: uv run pokepocketpedia-render-meta-report --snapshot-date 2026-02-08
```

Output:
- `data/processed/reports/YYYY-MM-DD/meta_overview.html`

Weekly all-in-one report generation:

```bash
ANTHROPIC_API_KEY=... uv run pokepocketpedia-generate-weekly-report
# optional: uv run pokepocketpedia-generate-weekly-report --snapshot-date 2026-02-08
```

Behavior:
- renders `meta_overview.html` for the snapshot
- checks top 10 decks by `count` from `top_decks.json`
- reuses existing `recommendation.<deck_slug>.html` from current or previous snapshots when found
- only calls LLM for decks that have no existing report artifact

Build static Pages site from generated reports:

```bash
uv run pokepocketpedia-build-site
# optional: uv run pokepocketpedia-build-site --snapshot-date 2026-02-08
```

Publish manually with GitHub Pages (no Actions required):
1. Run weekly generation, then run `pokepocketpedia-build-site`.
2. Commit `docs/` to your repo.
3. In GitHub repo settings, open Pages and set Source to `Deploy from a branch`.
4. Select your branch (for example `main`) and folder `/docs`.
5. Open the published Pages URL; `docs/index.html` is the landing page.

Normalize raw snapshots into processed artifacts:

```bash
uv run pokepocketpedia-normalize
```

Generate analytics metrics from processed artifacts:

```bash
uv run pokepocketpedia-analyze
```

## Output files

After ingestion, files are written to:

- `data/raw/cards/YYYY-MM-DD/cards.json`
- `data/raw/decks/YYYY-MM-DD/decks.json`
- `data/raw/decks/YYYY-MM-DD/decks_page.html`
- `data/raw/runs/YYYY-MM-DD/ingest_run.json`

Phase 2 normalized outputs:

- `data/processed/cards/YYYY-MM-DD/cards.normalized.json`
- `data/processed/decks/YYYY-MM-DD/decks.normalized.json`
- `data/processed/decks/YYYY-MM-DD/deck_cards.normalized.json`
- `data/processed/validation/YYYY-MM-DD/report.json`

Phase 3 analytics outputs:

- `data/processed/meta_metrics/YYYY-MM-DD/top_decks.json`
- `data/processed/meta_metrics/YYYY-MM-DD/top_cards.json`
- `data/processed/meta_metrics/YYYY-MM-DD/top_cards_by_archetype.json`
- `data/processed/meta_metrics/YYYY-MM-DD/trends_1d_7d.json`
- `data/processed/meta_metrics/YYYY-MM-DD/overview.json`

### `cards.json` structure
- `series_payload`: Pocket series metadata
- `sets`: set payloads
- `cards`: full card objects (card-level fields from TCGdex)
- `stats`: `set_count`, `card_count`

### `decks.json` structure
- `overview`: selected game/format/set and summary counts
- `decks`: parsed deck rows from Limitless table
  - includes rank, deck name, deck URL, matchup URL, count, share, win rate, icons
  - includes sample decklist crawl fields:
    - `sample_decklist_url`
    - `sample_decklist_urls`
    - `sample_deck_cards` (aggregated from sampled decklists)
    - `sample_deck_cards_count`
    - `sample_decklist_count`
- `stats`: `deck_count`

### Processed artifact metadata
- Processed and analytics artifacts include:
  - `artifact_type`
  - `schema_version` (current: `1.0.0`)

### Validation severity
- `data/processed/validation/YYYY-MM-DD/report.json` includes issue severities:
  - `info`
  - `warning`
  - `error`
- `pokepocketpedia-normalize` returns non-zero on validation `error`.
- `pokepocketpedia-run-daily` fails early if normalize status is `error`.

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
- runs `pokepocketpedia-run-daily` (ingest + normalize + analyze)

## Current scope status
- Phase 0: complete
- Phase 1 ingestion MVP: complete
- Phase 2 normalization: complete for core scope
- Phase 3 analytics: complete for core scope
- Phase 4 API: in progress (MVP implemented)
- Phase 5 recommendation: in progress (Anthropic MVP implemented)

See `project_plan.md` for roadmap and status.
