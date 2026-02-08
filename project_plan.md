# PokePocketPedia Project Plan

## 1) Project Goal
Build a daily updated web dashboard for Pokemon TCG Pocket meta analysis that:
- Ingests current card data (stats, pack, abilities, attacks).
- Ingests deck usage/meta data from Limitless Pocket.
- Produces analytics such as most popular decks/cards and trend signals.
- Uses LLM reasoning on structured data to recommend decks, card tech choices, and play strategy for ranked battles.
- Publishes a static, public dashboard via GitHub Pages.

## 2) Current Status (as of 2026-02-08)
- Phase 0: complete.
- Phase 1 MVP: complete for raw ingestion.
- Phase 2+: not started.

### Completed Work
- `uv`-based Python project scaffold with `pyproject.toml` and `uv.lock`.
- FastAPI bootstrap with route placeholders and `/health` endpoint.
- CI workflow for lint and tests.
- Daily workflow placeholder wired to `pokepocketpedia-run-daily`.
- Card ingestion from TCGdex:
  - series payload
  - set payloads
  - full per-card payloads
- Deck ingestion from Limitless:
  - raw HTML snapshot
  - parsed deck table rows (rank, count, share, win rate, links, icons)
  - page overview (game, format, set, tournaments/players/matches)
- Run metadata per snapshot (`ingest_run.json`) including source-level status.
- Test coverage for ingestion success, partial failure, and parser behavior.

### Known Gaps / Follow-up
- Deck card-composition extraction per archetype is not implemented yet.
- Normalized tables (`data/processed`) are not implemented yet.
- Retry/backoff and richer failure telemetry are still minimal.
- Daily workflow runs ingestion, but does not yet publish artifacts/pages.

## 3) Phase Roadmap

## Phase 0 - Project Structure and Environment Setup
### Status
- Complete.

### Deliverables (Done)
- `pyproject.toml` with project metadata and dependencies.
- `uv.lock` committed for deterministic installs.
- Basic package layout under `src/`.
- FastAPI app bootstrap.
- Tooling config for lint/test.
- `.github/workflows/` CI bootstrap.
- `.gitignore`, `.env.example`, `README.md`.

## Phase 1 - Card and Deck Data Ingestion
### Status
- MVP complete.

### Deliverables (Done)
- Ingestion jobs:
  - `pokepocketpedia-ingest`
  - `pokepocketpedia-run-daily` (currently maps to ingest)
- Raw snapshot storage convention:
  - `data/raw/cards/YYYY-MM-DD/cards.json`
  - `data/raw/decks/YYYY-MM-DD/decks.json`
  - `data/raw/decks/YYYY-MM-DD/decks_page.html`
  - `data/raw/runs/YYYY-MM-DD/ingest_run.json`
- Source metadata and run metadata (timestamp, source URL, status).

### Deliverables (Pending in Phase 1)
- Add robust retry/backoff policies and timeout controls.
- Add per-source metrics/logging for long-running fetches.
- Add optional persistent artifact upload strategy in CI.

## Phase 2 - Normalization and Data Contracts
### Objectives
- Transform raw payloads into canonical, analysis-ready tables.
- Build LLM-friendly card documents from normalized records.

### Deliverables
- Canonical tables:
  - `cards`
  - `decks`
  - `deck_cards`
  - `archetypes`
  - `meta_snapshot`
- LLM docs:
  - `card_docs_llm` JSONL (one card per document).
- Schema contracts and validation checks.
- Data quality checks (missing hp, attacks, pack mapping, etc.).

## Phase 3 - Analytics Engine
### Objectives
- Compute meta insights for dashboard and LLM usage.

### Deliverables
- Metrics:
  - Most popular decks (share percentage).
  - Most popular cards (overall + by archetype).
  - Trend deltas (1-day/7-day).
  - Optional placement-weighted strength proxy.
- Output artifacts:
  - `data/processed/meta_metrics/YYYY-MM-DD/*.json`
- Unit tests for metric calculations.

## Phase 4 - FastAPI Interaction Layer (Early Product Surface)
### Objectives
- Expose ingested/normalized/analytics data through FastAPI endpoints for local development and integration.

### Deliverables
- Endpoints (initial):
  - `/health`
  - `/cards`
  - `/decks`
  - `/metrics/top-decks`
  - `/metrics/top-cards`
  - `/recommendations/latest` (placeholder until Phase 5 complete)
- OpenAPI docs enabled.
- Basic pagination/filtering.

## Phase 5 - LLM Recommendation System
### Objectives
- Generate practical ranked-battle recommendations from structured meta + card data.

### Deliverables
- Recommendation pipelines:
  - Deck choice recommendations.
  - Card substitution/tech recommendations.
  - Matchup/play pattern strategy notes.
- Prompt templates constrained to current data only.
- Confidence labels and provenance metadata.
- Cached daily outputs to control cost and variability.

## Phase 6 - Dashboard and GitHub Pages Deployment
### Objectives
- Build and deploy public static dashboard with daily updates.

### Deliverables
- Dashboard pages:
  - Overview
  - Deck Meta
  - Card Usage
  - Recommendations
- Build process producing static assets in publish directory.
- GitHub Pages deploy workflow.

## 4) Data Storage Strategy (LLM-Friendly)
- Keep both:
  - Raw immutable snapshots (debugging, reprocessing, reproducibility).
  - Normalized analytical tables (fast stats + trend queries).
- Add LLM-oriented card docs with:
  - Clean textual summary.
  - Compact structured facts.
  - Tags for retrieval.
  - Snapshot/source provenance.

## 5) Suggested Initial Tech Stack
- Python `3.11+`
- `uv` for env/dependency/packaging workflows
- FastAPI + Uvicorn
- Pydantic models for contracts
- Pandas/Polars (choose one during implementation)
- Pytest for tests
- Ruff (lint/format)
- GitHub Actions + GitHub Pages

## 6) Next Practical Milestone
Implement Phase 2 normalization with these first outputs:
- `data/processed/cards/YYYY-MM-DD/cards.normalized.json`
- `data/processed/decks/YYYY-MM-DD/decks.normalized.json`
- `data/processed/decks/YYYY-MM-DD/deck_cards.normalized.json`
- Validation report per snapshot (`data/processed/validation/YYYY-MM-DD/report.json`)
