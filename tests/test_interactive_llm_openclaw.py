from __future__ import annotations

import json
from types import SimpleNamespace

from pokepocketpedia.recommend import interactive_llm


def _sample_output() -> dict:
    return {
        "executive_summary": "ok",
        "composition_assessment": "ok",
        "consistency_assessment": "ok",
        "meta_matchups": "ok",
        "alternatives_and_risks": ["risk"],
        "completion_plan": "",
        "recommended_additions": [],
        "confidence_and_limitations": "ok",
    }


def test_generate_interactive_analysis_openclaw(monkeypatch) -> None:
    fake_stdout = json.dumps({"payloads": [{"text": json.dumps(_sample_output())}]})

    def _fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=fake_stdout, stderr="")

    from pokepocketpedia.common import openclaw_client
    monkeypatch.setattr(openclaw_client.subprocess, "run", _fake_run)

    result = interactive_llm.generate_interactive_analysis(
        llm_input={"context": {}},
        mode="evaluation",
        provider="openclaw",
    )

    assert result["provider"] == "openclaw"
    assert result["output"]["executive_summary"] == "ok"


def test_generate_interactive_chat_reply_openclaw(monkeypatch) -> None:
    fake_stdout = json.dumps({"payloads": [{"text": "hello from openclaw"}]})
    captured_prompt = {"text": ""}

    def _fake_run(*args, **kwargs):
        cmd = args[0]
        message_idx = cmd.index("--message") + 1
        captured_prompt["text"] = cmd[message_idx]
        return SimpleNamespace(returncode=0, stdout=fake_stdout, stderr="")

    from pokepocketpedia.common import openclaw_client
    monkeypatch.setattr(openclaw_client.subprocess, "run", _fake_run)

    result = interactive_llm.generate_interactive_chat_reply(
        context_input={"context": {}},
        mode="evaluation",
        history=[],
        user_message="hi",
        provider="openclaw",
    )

    assert result["provider"] == "openclaw"
    assert result["reply"] == "hello from openclaw"
    assert "SKILL_CONTENT_BEGIN" in captured_prompt["text"]
