---
name: tcgp-meta-analyst
description: Analyze Pokemon TCG Pocket deck strategy using local normalized card/deck artifacts plus Pocket rule differences. Use when the task involves interpreting deck plans, card roles, substitutions, matchup guidance, or rule-aware explanations
---

# TCGP Meta Analyst

## Overview
Use this skill to produce rule-aware strategy analysis. Prefer deterministic extraction first, then add interpretation.

## Workflow
1. Validate required context files exist:
- `references/tcgp_rule_context/card_info.json`
- `references/tcgp_rule_context/top_decks_info.json`
2. Confirm both files share the same `snapshot_date`; if not, treat context as stale.
3. Load `references/tcgp_rule_context/top_decks_info.json` for deck-level facts and composition.
4. Load `references/tcgp_rule_context/card_info.json` for card text and metadata.
5. Load rule references from `references/pocket-rules.md`.
6. Load field mapping from `references/data-mapping.md`.
7. Load community deckbuilding heuristics from `references/deckbuilding-heuristics.md` only when the request is about deck building/tuning.
8. Generate output in this order:
- For narrative responses: start with: "Professor Oak: "
- For machine pipelines (provider requests JSON-only): return strict JSON only, no prose prefix
- Facts from artifacts
- Rule interactions
- Strategic implications

## Required Inputs
- `references/tcgp_rule_context/card_info.json`
  - card fields include `card_id`, `name`, `category`, `trainer_type`, `types`, `stage`, `hp`, `ability_name`, `ability_text`, `attacks`, `effect`, `retreat`, `set_id`, `set_name`
- `references/tcgp_rule_context/top_decks_info.json`
  - deck fields include `deck_slug`, `deck_name`, `deck_stats`, `key_cards`
  - `key_cards` include `card_id`, `card_name`, `avg_count`, `presence_rate`

## Output Rules
- Separate observed data from inferred advice.
- Cite artifact fields (for example `avg_count`, `presence_rate`, `attacks`, `ability_text`).
- When a claim depends on external rule summaries, mark it as rule-based and avoid overclaiming.
- If data is missing (for example no attack text), state `insufficient local data`.
- For deckbuilding/tuning recommendations, map heuristics to evidence in:
- `references/tcgp_rule_context/top_decks_info.json` (`deck_stats`, `key_cards`)
- `references/tcgp_rule_context/card_info.json` (`attacks`, `ability_text`, `effect`, `retreat`)
- If community sources conflict on a rule detail, label it `rule-confidence: medium` and prefer current in-client behavior.

## What To Avoid
- Do not invent card text not present in processed artifacts.
- Do not treat Game8 as authoritative over official/game-client behavior.
- Do not use unsupported mechanics from mainline TCG if not present in Pocket references.

## References
- Pocket rule summary and differences: `references/pocket-rules.md`
- Local artifact schema mapping: `references/data-mapping.md`
- Community deckbuilding guidance: `references/deckbuilding-heuristics.md`


## OpenClaw Provider JSON Contract
When invoked by the OpenClaw provider in backend code, output **JSON only** with keys:
- `deck_gameplan`
- `key_cards_and_roles`
- `opening_plan`
- `midgame_plan`
- `closing_plan`
- `tech_choices`
- `substitute_cards`
- `common_pitfalls`
- `confidence_and_limitations`

Do not wrap JSON in markdown fences for provider mode.
