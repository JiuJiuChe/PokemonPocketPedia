# PokePocketPedia

Pokemon TCG Pocket data pipeline, static report generator, API, and local web UI with LLM-assisted deck analysis.

## Prerequisites
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Node.js 18+ (for `webapp/`)
- Anthropic API key (`ANTHROPIC_API_KEY`) for all LLM generation features

## Setup

```bash
uv sync --extra dev
cp .env.example .env
```

## 1) How To Use It

### Core CLI commands (supported)

```bash
uv run pokepocketpedia-ingest
uv run pokepocketpedia-normalize
uv run pokepocketpedia-analyze
```

Run all three in one command:

```bash
uv run pokepocketpedia-run-daily
```

Optional ingestion controls:

```bash
# backfill a specific date
POKEPOCKETPEDIA_SNAPSHOT_DATE=2026-02-08 uv run pokepocketpedia-ingest

# crawl more deck archetype pages (default: 100; <=0 means all)
POKEPOCKETPEDIA_DECK_DETAIL_LIMIT=200 uv run pokepocketpedia-ingest

# sample more decklists per archetype (default: 3)
POKEPOCKETPEDIA_DECKLIST_SAMPLES_PER_ARCHETYPE=5 uv run pokepocketpedia-ingest
```

### Run the API

```bash
ANTHROPIC_API_KEY=... uv run uvicorn pokepocketpedia.api.main:app --reload
```

### LLM environment variables (recommended)

Set these in your shell (temporary):

```bash
export ANTHROPIC_API_KEY="<your_key>"
export POKEPOCKETPEDIA_ANTHROPIC_MODEL="claude-sonnet-4-5-20250929"
```

Or set per-command:

```bash
ANTHROPIC_API_KEY=... \
POKEPOCKETPEDIA_ANTHROPIC_MODEL=claude-sonnet-4-5-20250929 \
uv run pokepocketpedia-recommend --deck-slug hydreigon-mega-absol-ex-b1
```

If you use the minimal local provider path, you can also set:

```bash
export POKEPOCKETPEDIA_OPENCLAW_MODEL="openai-codex/gpt-5.3-codex"
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

The API serves generated report HTML files at:
- `/reports-static/<snapshot_date>/<file>.html`

### Main output folders
- Raw ingest: `data/raw/`
- Processed artifacts: `data/processed/`
- Generated reports: `data/processed/reports/`
- GitHub Pages site output: `docs/`

## 2) Pull Cards + Deck Info And Publish Static Report To GitHub Pages

### A. Pull and process data

```bash
uv run pokepocketpedia-run-daily
```

### B. Generate reports

Generate the weekly bundle (meta overview + top deck recommendation pages):

```bash
ANTHROPIC_API_KEY=... uv run pokepocketpedia-generate-weekly-report
# optional fixed snapshot
# ANTHROPIC_API_KEY=... uv run pokepocketpedia-generate-weekly-report --snapshot-date 2026-02-08
```

Generate meta overview only (no LLM):

```bash
uv run pokepocketpedia-render-meta-report
# optional: uv run pokepocketpedia-render-meta-report --snapshot-date 2026-02-08
```

Generate one deck recommendation page directly:

```bash
ANTHROPIC_API_KEY=... \
POKEPOCKETPEDIA_RECOMMEND_DECK_SLUG=hydreigon-mega-absol-ex-b1 \
uv run pokepocketpedia-recommend
```

### C. Build static site into `docs/`

```bash
uv run pokepocketpedia-build-site
# optional: uv run pokepocketpedia-build-site --snapshot-date 2026-02-08
```

This copies HTML reports into `docs/reports/<snapshot_date>/` and writes `docs/index.html`.

### D. Publish with GitHub Pages
1. Commit and push `docs/`.
2. In GitHub repo settings -> Pages, set source to `Deploy from a branch`.
3. Select branch (for example `main`) and folder `/docs`.
4. Open your Pages URL.

## 3) Launch Web Interface And Interact With LLM

Start backend first:

```bash
ANTHROPIC_API_KEY=... uv run uvicorn pokepocketpedia.api.main:app --reload
```

In a second terminal:

```bash
cd webapp
npm install
npm run dev
```

Open:
- `http://127.0.0.1:5173`

Notes:
- Vite proxies `/api` and `/reports-static` to backend `http://127.0.0.1:8000`.
- The Home tab reads report snapshots from `/api/reports/snapshots`.
- The Deck Builder uses interactive LLM endpoints:
  - `POST /api/interactive/deck-card-details`
  - `POST /api/interactive/evaluate-deck`
  - `POST /api/interactive/complete-deck`
  - `POST /api/interactive/chat-turn`
  - `GET /api/interactive/deck-template?deck_slug=...`

## Recommendation CLI (decoupled generate vs render)

Generate only JSON bundle (LLM call happens):

```bash
ANTHROPIC_API_KEY=... \
uv run pokepocketpedia-recommend --deck-slug hydreigon-mega-absol-ex-b1 --format json
```

Render markdown/html from an existing JSON bundle (no LLM call):

```bash
uv run pokepocketpedia-render-recommendation \
  --input data/processed/reports/YYYY-MM-DD/recommendation.hydreigon-mega-absol-ex-b1.json \
  --format all
```

## Test

```bash
uv run ruff check .
uv run pytest
```
