# PokePocketPedia Project Plan

## 1) Project Goal
Build a daily updated web dashboard for Pokemon TCG Pocket meta analysis that:
- Ingests current card data (stats, pack, abilities, attacks).
- Ingests deck usage/meta data from Limitless Pocket.
- Produces analytics such as most popular decks/cards and trend signals.
- Uses LLM reasoning on structured data to recommend decks, card tech choices, and play strategy for ranked battles.
- Publishes a static, public dashboard via GitHub Pages.

## 2) Core Product Requirements
- Daily automated data refresh.
- Reproducible historical snapshots for trend analysis.
- FastAPI endpoints for internal/dev interaction in early phases.
- LLM-ready data model (structured + textual card docs).
- CI/CD compatible with GitHub Actions from day one.

## 3) Phase Roadmap

## Phase 0 - Project Structure and Environment Setup
### Objectives
- Create a clean Python project scaffold using `uv`.
- Establish local/dev/prod parity for GitHub Actions.
- Lock down code quality, testing, and packaging conventions.

### Deliverables
- `pyproject.toml` with project metadata, dependencies, and optional groups (`dev`, `lint`, `test`).
- `uv.lock` committed for deterministic installs.
- Basic package layout under `src/`.
- FastAPI app bootstrap (health endpoint + API router skeleton).
- Tooling config files (formatter/linter/type checker/test).
- `.github/workflows/` bootstrap CI for lint + tests.
- `.gitignore`, `.env.example`, `README.md`.

### Proposed Initial Structure
- `src/pokepocketpedia/__init__.py`
- `src/pokepocketpedia/api/main.py`
- `src/pokepocketpedia/api/routes/`
- `src/pokepocketpedia/ingest/`
- `src/pokepocketpedia/normalize/`
- `src/pokepocketpedia/analyze/`
- `src/pokepocketpedia/recommend/`
- `src/pokepocketpedia/storage/`
- `scripts/`
- `data/raw/`
- `data/processed/`
- `data/llm/`
- `tests/`
- `.github/workflows/`

### Environment and Packaging Decisions
- Use `uv` for:
  - Virtual environment management.
  - Dependency installation/sync.
  - Lockfile management.
  - Package build/publish workflow (when ready).
- Keep all runtime code importable as a package (`src/` layout).
- Add CLI entry points for pipeline tasks (`ingest`, `normalize`, `analyze`, `recommend`, `build-site`).

### GitHub Actions Considerations in Phase 0
- Add CI workflow to:
  - Install Python via `actions/setup-python`.
  - Install `uv`.
  - Run `uv sync --frozen`.
  - Run lint + tests.
- Pin Python versions (for example 3.11/3.12 matrix if needed).
- Ensure all scripts run non-interactively (required for CI).

## Phase 1 - Card and Deck Data Ingestion
### Objectives
- Ingest Pokemon TCG Pocket card data from TCGdex (primary source).
- Ingest deck/meta usage from Limitless Pocket.
- Persist raw snapshots per day.

### Deliverables
- Ingestion jobs:
  - `ingest_cards`
  - `ingest_decks`
- Raw snapshot storage convention:
  - `data/raw/cards/YYYY-MM-DD/*.json`
  - `data/raw/decks/YYYY-MM-DD/*.json`
- Source metadata and run metadata (timestamp, source URL, status).
- Basic retry/backoff and graceful failure logs.

### GitHub Actions Considerations
- Scheduled workflow (`cron`) runs ingestion daily.
- Manual trigger via `workflow_dispatch`.
- Artifact retention or direct commit strategy decided early.

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

### GitHub Actions Considerations
- Validation step fails pipeline on schema/data quality breakage.
- Cache dependencies but not mutable data outputs unless intentional.

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

### GitHub Actions Considerations
- Deterministic analytics execution in CI.
- Preserve daily snapshots for trend chart windows (for example 90 days).

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

### GitHub Actions Considerations
- API tests run in CI.
- Optional startup smoke test in workflow.

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

### GitHub Actions Considerations
- LLM step guarded by secrets availability.
- Fallback mode: publish dashboard without fresh recommendations if LLM fails.

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

### GitHub Actions Considerations
- End-to-end daily workflow:
  1. Sync environment with `uv`.
  2. Ingest data.
  3. Normalize and validate.
  4. Compute analytics.
  5. Generate recommendations.
  6. Build static site.
  7. Deploy to Pages.
- Use concurrency control to avoid overlapping scheduled runs.

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

## 6) Risks and Mitigations
- Source schema drift:
  - Mitigate with contract validation + alerting in CI.
- Third-party rate limits or downtime:
  - Mitigate with retries and fallback to previous valid snapshot.
- LLM variability:
  - Mitigate with structured prompts, constrained inputs, and caching.
- Deployment instability:
  - Mitigate with phased workflows and smoke tests before deploy.

## 7) Definition of Done (MVP)
- Daily automated pipeline runs in GitHub Actions.
- Dashboard publishes to GitHub Pages automatically.
- Shows top decks, top cards, and recent trends.
- Includes one daily LLM recommendation section with source-aware reasoning.
- Pipeline failures are observable and do not silently publish broken data.
