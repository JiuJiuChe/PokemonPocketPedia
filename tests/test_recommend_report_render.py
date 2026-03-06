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



def test_render_recommendation_html_falls_back_to_card_page_image(monkeypatch) -> None:
    from pokepocketpedia.recommend import report_render
    from pokepocketpedia.common import image_utils

    context_payload = {
        "snapshot_date": "2026-03-05",
        "deck_slug": "suicune-ex-a4a-baxcalibur-b2a",
        "llm_input": {
            "context": {
                "target_deck": {
                    "deck_name": "Suicune ex Baxcalibur",
                    "share_pct": 5.0,
                    "win_rate_pct": 52.1,
                    "rank": 1,
                },
                "deck_card_grid": [
                    {
                        "card_name": "Baxcalibur",
                        "avg_count": 2.0,
                        "presence_rate": 1.0,
                        "image_url": "https://assets.tcgdex.net/en/tcgp/B2a/36/high.webp",
                        "card_url": "https://pocket.limitlesstcg.com/cards/B2a/36",
                    }
                ],
            }
        },
    }
    llm_result = {
        "provider": "openclaw",
        "model": "openai-codex/gpt-5.3-codex",
        "generated_at": "2026-03-05T00:00:00+00:00",
        "usage": {},
        "structured_output": {
            "deck_gameplan": "Plan",
            "key_cards_and_roles": ["Baxcalibur: core"],
            "opening_plan": "Open",
            "midgame_plan": "Mid",
            "closing_plan": "Close",
            "tech_choices": ["Tech"],
            "substitute_cards": [],
            "common_pitfalls": ["Pitfall"],
            "confidence_and_limitations": "OK",
        },
    }

    monkeypatch.setattr(
        image_utils,
        "image_from_card_page",
        lambda card_url: "https://assets.limitlesstcg.com/fallback/baxcalibur.webp",
    )

    html = render_recommendation_html(context_payload=context_payload, llm_result=llm_result)
    assert "https://assets.limitlesstcg.com/fallback/baxcalibur.webp" in html



def test_render_recommendation_html_key_roles_use_card_page_fallback(monkeypatch) -> None:
    from pokepocketpedia.recommend import report_render
    from pokepocketpedia.common import image_utils

    context_payload = {
        "snapshot_date": "2026-03-05",
        "deck_slug": "suicune-ex-a4a-baxcalibur-b2a",
        "llm_input": {
            "context": {
                "target_deck": {"deck_name": "Suicune ex Baxcalibur", "win_rate_pct": 52.1, "rank": 1},
                "deck_card_grid": [
                    {
                        "card_name": "Baxcalibur",
                        "avg_count": 2.0,
                        "presence_rate": 1.0,
                        "image_url": "https://assets.tcgdex.net/en/tcgp/B2a/36/high.webp",
                        "card_url": "https://pocket.limitlesstcg.com/cards/B2a/36",
                    }
                ],
            }
        },
    }
    llm_result = {
        "provider": "openclaw",
        "model": "openai-codex/gpt-5.3-codex",
        "generated_at": "2026-03-05T00:00:00+00:00",
        "usage": {},
        "structured_output": {
            "deck_gameplan": "Plan",
            "key_cards_and_roles": ["Baxcalibur: core finisher"],
            "opening_plan": "Open",
            "midgame_plan": "Mid",
            "closing_plan": "Close",
            "tech_choices": ["Tech"],
            "substitute_cards": [],
            "common_pitfalls": ["Pitfall"],
            "confidence_and_limitations": "OK",
        },
    }

    monkeypatch.setattr(
        image_utils,
        "image_from_card_page",
        lambda card_url: "https://assets.limitlesstcg.com/fallback/baxcalibur-role.webp",
    )

    html = render_recommendation_html(context_payload=context_payload, llm_result=llm_result)
    import re
    m = re.search(r'<article class=\"role-row\">.*?</article>', html, re.S)
    assert m is not None
    assert "https://assets.limitlesstcg.com/fallback/baxcalibur-role.webp" in m.group(0)
