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
- Phase 2: complete for core scope.
- Phase 3: complete for core scope.
- Phase 4: in progress (API MVP implemented).
- Phase 5: in progress (Anthropic MVP implemented).
- Phase 6: not started.
- Interactive Web App Program: planning complete, implementation started.

### Completed Work
- `uv`-based Python scaffold with CI, tests, lint, and FastAPI bootstrap.
- Raw ingestion:
  - cards from TCGdex (series, sets, full card payloads)
  - decks from Limitless (table parse + overview)
  - deck detail crawling via sampled tournament decklists per archetype
- Ingest progress bars and run metadata.
- Normalization outputs:
  - `cards.normalized.json`
  - `decks.normalized.json`
  - `deck_cards.normalized.json`
  - validation report with severity (`info`/`warning`/`error`)
  - schema metadata (`artifact_type`, `schema_version`)
  - runtime JSON schema validation for all processed normalization artifacts
- Analytics outputs:
  - `top_decks.json`
  - `top_cards.json`
  - `top_cards_by_archetype.json`
  - `trends_1d_7d.json`
  - `overview.json`
  - nearest-prior fallback references for 1d/7d trend anchors
- Daily CLI pipeline now runs ingest + normalize + analyze.
- Phase 4 API MVP:
  - data-backed endpoints for cards/decks/metrics/recommendations
  - snapshot selection (latest or explicit date)
  - filtering and pagination on list endpoints
  - endpoint tests for contracts and error handling
- Phase 5 recommendation MVP:
  - `GET /recommendations/context` for deck-specific LLM context bundles
  - `POST /recommendations/generate` using Anthropic (`Claude Sonnet 4.5`)
  - CLI `pokepocketpedia-recommend` for end-to-end generation
  - report rendering to Markdown + HTML under processed reports

### Known Gaps / Follow-up
- Daily workflow still does not publish dashboard/pages.
- Retry/backoff and richer failure telemetry are still minimal.

## 3) Phase Roadmap

## Phase 0 - Project Structure and Environment Setup
### Status
- Complete.

## Phase 1 - Card and Deck Data Ingestion
### Status
- MVP complete.

### Remaining hardening tasks
- Add robust retry/backoff/timeouts per source.
- Add structured error classes and clearer failure diagnostics.
- Decide CI artifact strategy (commit snapshots vs artifact retention vs external storage).

## Phase 2 - Normalization and Data Contracts
### Status
- Complete for core scope.

### Implemented
- `pokepocketpedia-normalize` command.
- Processed outputs for cards, decks, deck_cards.
- Validation report with core counts and warnings.

### Remaining hardening tasks
- Stronger data quality checks.
- Required-field checks and duplicate checks are implemented; range/domain checks are still limited.
- Canonical mapping hardening.
  - Resolve edge cases where card identity is ambiguous across ids/names.
- Deck-card coverage policy.
  - Current approach uses sampled decklists per archetype; add optional full-coverage mode and quality flags.

## Phase 3 - Analytics Engine
### Status
- Complete for core scope.

### Implemented
- `pokepocketpedia-analyze` command.
- Top deck metrics and top card metrics from normalized data.
- Archetype-split card analytics (`top_cards_by_archetype.json`).
- 1-day and 7-day trend deltas with nearest-prior fallback references.
- Overview file with most popular deck/card highlights.

### Remaining hardening tasks
- Richer archetype taxonomy/merging for related deck families.
- Matchup-aware analytics.
  - Integrate matchup data where available.
- Metric methodology docs.
  - Document formulas, assumptions, and interpretation limits.
- Multi-day regression tests.
  - Validate metric stability and expected changes across snapshot sequences.

## Phase 4 - FastAPI Interaction Layer (Early Product Surface)
### Status
- In progress (API MVP done).

### Implemented
- Data-backed endpoints for cards/decks/metrics/recommendations.
- Filtering/pagination and response contracts.

### Remaining hardening tasks
- Add Pydantic response models for stricter typed contracts/OpenAPI docs.
- Add endpoint auth/rate-limit policy if public API exposure is planned.
- Add caching strategy for high-traffic metric endpoints.
- Add request/response examples in README.

## Phase 5 - LLM Recommendation System
### Status
- In progress (MVP done).

### Implemented
- LLM input/context preparation for user-specified deck slugs.
- Anthropic-backed strategy generation endpoint and CLI integration.
- Structured output normalization with fallback handling for malformed model responses.
- Human-readable report generation (`.md` and `.html`) for interpretation.

### Remaining hardening tasks
- Persist generated recommendation payloads as JSON artifacts for audit/versioning.
- Add deterministic prompt/version tagging in generated outputs.
- Add weekly scheduled recommendation workflow with secret wiring and output publishing.
- Add quality checks against empty/low-signal outputs (minimum section length, required evidence).

## Phase 6 - Dashboard and GitHub Pages Deployment
### Status
- Not started.

### Planned deliverables
- Static dashboard pages and charts.
- Pages deployment workflow and failure-safe publish behavior.

## Interactive Web App Program (Local First -> NAS Later)
### Phase A - Local Web Foundation
### Status
- Complete.

### Scope
- Build and run a local web app on `localhost` before any NAS deployment.
- Keep GitHub Pages static reports as-is.
- Select framework stack for interactive experience:
  - Frontend: React + Vite + TypeScript
  - Backend: FastAPI (reuse existing services and data pipeline)

### Deliverables
- Local frontend scaffold with tab navigation and API client wiring.
- FastAPI CORS/static configuration for local frontend development.
- Local run instructions for backend + frontend.

## Phase B - Data & API Integration for Interactive App
### Status
- Complete for core scope.

### Deliverables
- API endpoints/contracts:
  - latest snapshot/report discovery (`/reports/snapshots`, `/reports/latest`)
  - card search/filter for deck building (`/cards`)
  - deck card detail lookup for selected cards (`/interactive/deck-card-details`)
- Interactive UI integration:
  - deck builder tabs can fetch/render selected-card metadata and meta usage stats.
- Core typed response contract implemented for selected-card details endpoint.

## Phase C - Interactive Deck Builder UX
### Status
- Complete for core scope.

### Deliverables
- Interactive page that supports:
  - card search and selection
  - selected deck state management
  - hard limit checks (20-card deck target)
- Shared UX components for tabbed navigation and result panels.

### Implemented notes
- Two-panel deck builder layout (left: selection/actions, right: selected deck grid).
- Auto-loaded selected-card details (image + status + meta presence).
- Guardrails: prevent deck size above 20 and prevent more than 2 copies for the same card name.

## Phase D - LLM Interaction Features (Combined)
### Status
- Planned.

### Deliverables
- Deck evaluation flow:
  - user selects exactly 20 cards
  - LLM evaluates deck quality, game plan, and risks
- Deck completion flow:
  - user selects fewer than 20 cards
  - local candidate generation + LLM completion recommendations
- Structured output format and confidence/limitations fields.

## Phase E - Hardening and Validation
### Status
- Planned.

### Deliverables
- Prompt/version tagging and request traceability.
- Validation and guardrails for low-signal or malformed outputs.
- Cost controls and caching for repeated interactive evaluations.
- Integration tests for interactive API paths.

## Phase F - NAS Deployment
### Status
- Planned.

### Deliverables
- Containerized deploy (frontend + backend) on NAS.
- Secret management and reverse proxy routing.
- Operational runbook for weekly manual updates.

## 4) Data Storage Strategy (LLM-Friendly)
- Keep both:
  - Raw immutable snapshots (debugging, reprocessing, reproducibility).
  - Normalized analytical tables (fast stats + trend queries).
- Add LLM-oriented docs with structured facts + provenance in later phases.

## 5) Suggested Initial Tech Stack
- Python `3.11+`
- `uv` for env/dependency/packaging workflows
- FastAPI + Uvicorn
- Pydantic models for contracts
- Pytest + Ruff
- GitHub Actions + GitHub Pages

## 6) Next Practical Milestone
Complete Interactive Web App Phase A local foundation:
- Add local frontend scaffold with tabbed layout (Home + interactive deck tools).
- Wire frontend to existing FastAPI APIs on localhost.
- Add local development run instructions and verify end-to-end connectivity.
