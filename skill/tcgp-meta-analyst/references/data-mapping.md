# Local Data Mapping For Rule-Aware Analysis

## Card Artifact
File pattern:
- `data/processed/cards/<snapshot>/cards.normalized.json`

Useful fields per card item:
- `card_id`
- `name`
- `category`
- `trainer_type`
- `hp`
- `types`
- `stage`
- `ability_name`
- `ability_text`
- `attacks[]` with `name`, `cost`, `damage`, `effect`
- `effect`
- `retreat`
- `set_id`, `set_name`

## Deck Composition Artifact
File pattern:
- `data/processed/decks/<snapshot>/deck_cards.normalized.json`

Useful fields per row:
- `deck_slug`, `deck_name`
- `card_id`, `card_name`
- `avg_count`
- `presence_rate`
- `sample_count`
- `sample_decklist_count`

Interpretation hints:
- Higher `presence_rate` approximates core inclusion confidence.
- Higher `avg_count` approximates slot priority.
- Use both together before labeling a card as mandatory or flexible.

## Meta Metrics (Optional)
File patterns:
- `data/processed/meta_metrics/<snapshot>/top_decks.json`
- `data/processed/meta_metrics/<snapshot>/top_cards.json`

Useful fields:
- Deck: `count`, `win_rate_pct`, `deck_name`, `slug`
- Card: `avg_presence_rate`, `weighted_share_points`, `card_name`, `card_id`

## Safe Inference Rules
- Infer role confidence only when `presence_rate` and `avg_count` agree.
- Use `ability_text`/`attacks.effect` for tactical lines only when present.
- Mark unknown when text/effects are missing in local artifacts.
