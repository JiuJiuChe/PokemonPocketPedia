# Local Data Mapping For Rule-Aware Analysis

## Skill-Local Context Files
Use these files under the skill folder:
- `references/tcgp_rule_context/card_info.json`
- `references/tcgp_rule_context/top_decks_info.json`

Both files include `snapshot_date`; treat mismatched dates as stale context.

## Card Info Artifact
File:
- `references/tcgp_rule_context/card_info.json`

Top-level fields:
- `snapshot_date`
- `artifact_sources.cards`
- `cards[]`

Useful fields per `cards[]` item:
- `card_id`
- `name`
- `category`
- `trainer_type`
- `types`
- `stage`
- `hp`
- `ability_name`
- `ability_text`
- `attacks[]` with `name`, `cost`, `damage`, `effect`
- `effect`
- `retreat`
- `set_id`, `set_name`

## Top Decks Info Artifact
File:
- `references/tcgp_rule_context/top_decks_info.json`

Top-level fields:
- `snapshot_date`
- `rule_profile`
- `artifact_sources.decks`
- `artifact_sources.deck_cards`
- `decks[]`

Useful fields per `decks[]` item:
- `deck_slug`, `deck_name`
- `deck_stats.rank`
- `deck_stats.share_pct`
- `deck_stats.win_rate_pct`
- `deck_stats.count`
- `deck_stats.players`
- `deck_stats.matches`
- `deck_stats.match_record`
- `deck_stats.set_code`, `deck_stats.set_name`
- `key_cards[]` with:
  - `card_id`, `card_name`
  - `avg_count`
  - `presence_rate`

## Join Rules
- Join `decks[].key_cards[].card_id` to `card_info.cards[].card_id` for card text/details.
- Treat `key_cards` as composition signal only; do not assume it carries full effect text.
- If join misses (missing `card_id` or missing card row), report `insufficient local data`.

## Interpretation Hints
- Higher `presence_rate` approximates core inclusion confidence.
- Higher `avg_count` approximates slot priority.
- Use `presence_rate` + `avg_count` together before labeling a card as mandatory or flexible.
- Use `share_pct` and `win_rate_pct` to contextualize deck-level strength and prevalence.

## Safe Inference Rules
- Infer role confidence only when composition signals and card text support each other.
- Use `ability_text`/`attacks.effect` for tactical lines only when present in `card_info.json`.
- Mark unknown when text/effects are missing in local artifacts.
