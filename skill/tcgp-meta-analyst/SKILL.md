---
name: tcgp-meta-analyst
description: Analyze Pokemon TCG Pocket deck strategy using normalized artifacts and Pocket rule differences. Use when the task involves interpreting deck plans, card roles, substitutions, matchup guidance, or rule-aware explanations
---

# TCGP Meta Analyst

## Overview
Use this skill to produce rule-aware strategy analysis. Prefer deterministic extraction first, then add interpretation.

## Source-Of-Truth Priority (Critical)
When this skill is invoked from PokemonPocketPedia recommendation/interactive pipelines:
1. **Primary source of truth**: `LLM_INPUT.context` (injected by backend pipeline).
2. **Secondary references**: skill-local files under `references/`.
3. If primary and secondary conflict, **prefer `LLM_INPUT.context`** and record the mismatch in `confidence_and_limitations`.

Do not treat skill-local references as mandatory when `LLM_INPUT.context` is present.

## Context Handling
1. If `LLM_INPUT.context` exists, use it as the main evidence for deck/card/meta claims.
2. Optionally use skill-local references to clarify rules or fill missing text fields:
   - `references/tcgp_rule_context/card_info.json`
   - `references/tcgp_rule_context/top_decks_info.json`
   - `references/pocket-rules.md`
   - `references/data-mapping.md`
   - `references/deckbuilding-heuristics.md` (only for deckbuilding/tuning tasks)
3. If both local JSON references exist, compare `snapshot_date` values.
4. If local `snapshot_date` is stale relative to `LLM_INPUT.context.snapshot_date` (or clearly inconsistent), keep using `LLM_INPUT.context` and annotate the stale-reference limitation.

## Output Mode Rules (Critical)
Choose mode from the caller contract:

### A) Provider JSON mode (PokemonPocketPedia backend/OpenClaw provider path)
- Return **strict JSON object only**.
- No prefix, no suffix, no markdown fences, no commentary.
- **Never** prepend `Professor Oak:` in this mode.

### B) Narrative/chat mode
- Use natural prose.
- You may start with `Professor Oak: ` only in this mode.

If uncertain, default to JSON-only when a schema contract is provided.

## Required Output Contract (Provider JSON mode)
Return JSON with keys:
- `deck_gameplan`
- `key_cards_and_roles`
- `opening_plan`
- `midgame_plan`
- `closing_plan`
- `tech_choices`
- `substitute_cards`
- `common_pitfalls`
- `confidence_and_limitations`

Do not wrap JSON in markdown fences.

## Evidence Rules
- Separate observed data from inferred advice.
- Cite artifact fields when making claims (for example `avg_count`, `presence_rate`, `attacks`, `ability_text`, `effect`).
- When a claim depends on rule summaries, mark as rule-based and avoid overclaiming.
- If necessary data is missing, explicitly state `insufficient local data`.
- If local references are stale/conflicting vs `LLM_INPUT.context`, mention that in `confidence_and_limitations`.

## Deckbuilding/Tuning Rules
Use `references/deckbuilding-heuristics.md` only when deck building/tuning is requested.
Map recommendations to available evidence in:
- `LLM_INPUT.context` (preferred)
- `references/tcgp_rule_context/top_decks_info.json` (`deck_stats`, `key_cards`) when applicable
- `references/tcgp_rule_context/card_info.json` (`attacks`, `ability_text`, `effect`, `retreat`) when applicable

If community sources conflict on a rule detail, label `rule-confidence: medium` and prefer current in-client behavior.

## What To Avoid
- Do not invent card text not present in available artifacts/context.
- Do not treat Game8 as authoritative over official/game-client behavior.
- Do not use unsupported mechanics from mainline TCG if not present in Pocket references.

## References
- Pocket rule summary and differences: `references/pocket-rules.md`
- Local artifact schema mapping: `references/data-mapping.md`
- Community deckbuilding guidance: `references/deckbuilding-heuristics.md`
