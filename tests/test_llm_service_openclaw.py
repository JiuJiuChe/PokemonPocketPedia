from __future__ import annotations

import json
from types import SimpleNamespace

from pokepocketpedia.recommend import llm_service


def test_generate_recommendation_routes_openclaw(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_service,
        "generate_with_openclaw",
        lambda llm_input, model=None: {"provider": "openclaw", "structured_output": {}},
    )

    result = llm_service.generate_recommendation({"context": {}}, provider="openclaw")

    assert result["provider"] == "openclaw"


def test_generate_with_openclaw_parses_json_payload(monkeypatch) -> None:
    payload = {
        "deck_gameplan": "plan",
        "key_cards_and_roles": ["A"],
        "opening_plan": "open",
        "midgame_plan": "mid",
        "closing_plan": "close",
        "tech_choices": ["tech"],
        "substitute_cards": [],
        "common_pitfalls": ["pitfall"],
        "confidence_and_limitations": "ok",
    }
    fake_stdout = json.dumps({"payloads": [{"text": json.dumps(payload)}]})

    def _fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=fake_stdout, stderr="")

    from pokepocketpedia.common import openclaw_client
    monkeypatch.setattr(openclaw_client.subprocess, "run", _fake_run)

    result = llm_service.generate_with_openclaw({"context": {}}, model="test-model")

    assert result["provider"] == "openclaw"
    assert result["model"] == "test-model"
    assert result["structured_output"]["deck_gameplan"] == "plan"
