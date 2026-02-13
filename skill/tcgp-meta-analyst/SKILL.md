---
name: tcgp-meta-analyst
description: Analyze Pokemon TCG Pocket deck strategy using local normalized card/deck artifacts plus Pocket rule differences. Use when the task involves interpreting deck plans, card roles, substitutions, matchup guidance, or rule-aware explanations for Pocket ranked play from files like data/processed/cards/*/cards.normalized.json, data/processed/decks/*/deck_cards.normalized.json, and data/processed/meta_metrics/*.
---

# TCGP Meta Analyst

## Overview
Use this skill to produce rule-aware strategy analysis from local PokePocketPedia artifacts.
Prefer deterministic extraction first, then add interpretation.

## Workflow
1. Resolve snapshot date from the newest processed artifacts unless user specifies one.
2. Build a compact analysis context with `scripts/build_rule_context.py`.
3. Load rule references from `references/pocket-rules.md`.
4. Map card/deck fields using `references/data-mapping.md`.
5. Generate output in this order:
- Facts from artifacts
- Rule interactions
- Strategic implications
- Confidence/limits

## Required Inputs
- `data/processed/cards/<snapshot>/cards.normalized.json`
- `data/processed/decks/<snapshot>/deck_cards.normalized.json`
- Optional: `data/processed/meta_metrics/<snapshot>/top_decks.json`
- Optional: `data/processed/meta_metrics/<snapshot>/top_cards.json`

## Quick Commands
```bash
python skill/tcgp-meta-analyst/scripts/build_rule_context.py \
  --snapshot-date 2026-02-08 \
  --out /tmp/tcgp_rule_context.json
```

If `--snapshot-date` is omitted, the script picks the latest shared snapshot under processed cards/decks.

## Output Rules
- Separate observed data from inferred advice.
- Cite artifact fields (for example `avg_count`, `presence_rate`, `attacks`, `ability_text`).
- When a claim depends on external rule summaries, mark it as rule-based and avoid overclaiming.
- If data is missing (for example no attack text), state `insufficient local data`.

## What To Avoid
- Do not invent card text not present in processed artifacts.
- Do not treat Game8 as authoritative over official/game-client behavior.
- Do not use unsupported mechanics from mainline TCG if not present in Pocket references.

## References
- Pocket rule summary and differences: `references/pocket-rules.md`
- Local artifact schema mapping: `references/data-mapping.md`
