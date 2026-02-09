from __future__ import annotations

from pokepocketpedia.recommend.report_render import (
    render_recommendation_html,
    render_recommendation_markdown,
)


def test_render_recommendation_markdown_and_html() -> None:
    context_payload = {
        "snapshot_date": "2026-02-09",
        "deck_slug": "hydreigon-mega-absol-ex-b1",
        "llm_input": {
            "context": {
                "target_deck": {
                    "deck_name": "Hydreigon Mega Absol ex",
                    "share_pct": 15.13,
                    "win_rate_pct": 53.43,
                    "rank": 1,
                },
                "deck_card_grid": [
                    {
                        "card_name": "Hydreigon",
                        "avg_count": 2.0,
                        "presence_rate": 1.0,
                        "image_url": "https://assets.tcgdex.net/en/tcgp/B1/157",
                    },
                    {
                        "card_name": "Deino",
                        "avg_count": 2.0,
                        "presence_rate": 1.0,
                        "image_url": "https://assets.tcgdex.net/en/tcgp/B1/155",
                    },
                    {
                        "card_name": "Rare Candy",
                        "avg_count": 2.0,
                        "presence_rate": 1.0,
                        "image_url": "https://assets.tcgdex.net/en/tcgp/A3/144",
                    }
                ],
            }
        },
    }
    llm_result = {
        "provider": "anthropic",
        "model": "claude-sonnet-4-5-20250929",
        "generated_at": "2026-02-09T00:00:00+00:00",
        "usage": {"input_tokens": 123, "output_tokens": 456},
        "structured_output": {
            "deck_gameplan": "Control tempo and preserve evolutions.",
            "key_cards_and_roles": [
                "Hydreigon (B1-157): finisher",
                "Deino (B1-155): setup",
                "Rare Candy (A3-144): evolve Deino directly into Hydreigon",
            ],
            "opening_plan": "Set up basics quickly.",
            "midgame_plan": "Trade efficiently.",
            "closing_plan": "Sequence finisher safely.",
            "tech_choices": ["+1 disruption slot"],
            "common_pitfalls": ["Overcommitting resources"],
            "confidence_and_limitations": "Good confidence with current sample size.",
        },
    }

    markdown = render_recommendation_markdown(
        context_payload=context_payload,
        llm_result=llm_result,
    )
    html = render_recommendation_html(
        context_payload=context_payload,
        llm_result=llm_result,
    )

    assert "Deck Recommendation Report" in markdown
    assert "Hydreigon Mega Absol ex" in markdown
    assert "Deck cards" in markdown
    assert "Control tempo and preserve evolutions." in markdown
    assert "<html" in html
    assert "Deck cards" in html
    assert "card-tile" in html
    assert "/high.webp" in html
    assert "Hydreigon Mega Absol ex" in html
    assert 'alt="Rare Candy"' in html


def test_render_recommendation_markdown_with_missing_sections_uses_fallbacks() -> None:
    context_payload = {
        "snapshot_date": "2026-02-09",
        "deck_slug": "hydreigon-mega-absol-ex-b1",
        "llm_input": {
            "context": {
                "target_deck": {"deck_name": "Hydreigon Mega Absol ex"},
                "key_cards_from_samples": [
                    {"card_name": "Hydreigon", "avg_count": 2.0, "presence_rate": 1.0}
                ],
            }
        },
    }
    llm_result = {
        "provider": "anthropic",
        "model": "claude-sonnet-4-5-20250929",
        "generated_at": "2026-02-09T00:00:00+00:00",
        "usage": {},
        "structured_output": {},
        "raw_text": "Free-form response.",
    }

    markdown = render_recommendation_markdown(
        context_payload=context_payload,
        llm_result=llm_result,
    )
    assert "Model did not provide a full gameplan section." in markdown
    assert "Hydreigon (avg_count=2.0, presence_rate=1.0)" in markdown
    assert "Raw Model Response" in markdown
