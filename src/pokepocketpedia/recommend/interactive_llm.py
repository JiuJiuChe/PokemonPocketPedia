"""Interactive LLM analysis for custom deck evaluation/completion."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from os import getenv
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _system_prompt(mode: str) -> str:
    base = (
        "You are a competitive Pokemon TCG Pocket strategy analyst. "
        "Evaluate only from provided JSON context and explicit game rules. "
        "Use practical ladder-focused guidance. "
        "Explicitly apply the tcgp-meta-analyst skill instructions in your reasoning."
    )
    if mode == "completion":
        return (
            f"{base} Complete missing slots for an incomplete deck while preserving "
            "coherent game plan. "
            "For proposed additions, keep total deck size at exactly 20 cards."
        )
    return (
        f"{base} Evaluate the provided 20-card deck and identify improvements."
    )


def _extract_text_content(message: Any) -> str:
    content = getattr(message, "content", [])
    parts: list[str] = []
    for block in content:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def _extract_tool_input(message: Any) -> dict[str, Any] | None:
    content = getattr(message, "content", [])
    for block in content:
        if getattr(block, "type", None) != "tool_use":
            continue
        payload = getattr(block, "input", None)
        if isinstance(payload, dict):
            return payload
    return None


def _parse_json_response(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_additions(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if not isinstance(item, dict):
            continue
        card_name = str(item.get("card_name") or "").strip()
        reason = str(item.get("reason") or "").strip()
        count_raw = item.get("count")
        if not card_name:
            continue
        count = int(count_raw) if isinstance(count_raw, int) and count_raw > 0 else 1
        out.append(
            {
                "card_name": card_name,
                "count": count,
                "reason": reason,
            }
        )
    return out


def _default_output(mode: str, reason: str) -> dict[str, Any]:
    base = {
        "executive_summary": "Model output unavailable; generated fallback response.",
        "composition_assessment": "N/A",
        "consistency_assessment": "N/A",
        "meta_matchups": "N/A",
        "alternatives_and_risks": ["N/A"],
        "completion_plan": "N/A" if mode == "completion" else "",
        "recommended_additions": [],
        "confidence_and_limitations": f"Fallback used. Reason: {reason}",
    }
    if mode != "completion":
        base["completion_plan"] = ""
    return base


def _normalize_output(payload: dict[str, Any] | None, mode: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _default_output(mode, "No valid JSON payload returned.")

    out = {
        "executive_summary": _normalize_text(payload.get("executive_summary")),
        "composition_assessment": _normalize_text(payload.get("composition_assessment")),
        "consistency_assessment": _normalize_text(payload.get("consistency_assessment")),
        "meta_matchups": _normalize_text(payload.get("meta_matchups")),
        "alternatives_and_risks": _normalize_list(payload.get("alternatives_and_risks")),
        "completion_plan": _normalize_text(payload.get("completion_plan")),
        "recommended_additions": _normalize_additions(payload.get("recommended_additions")),
        "confidence_and_limitations": _normalize_text(payload.get("confidence_and_limitations")),
    }

    required = [
        "executive_summary",
        "composition_assessment",
        "consistency_assessment",
        "meta_matchups",
        "alternatives_and_risks",
        "confidence_and_limitations",
    ]
    if mode == "completion":
        required.append("completion_plan")
    missing = [key for key in required if not out.get(key)]
    if missing:
        fallback = _default_output(mode, f"Missing fields: {', '.join(missing)}")
        for key in missing:
            out[key] = fallback[key]
    return out


def generate_interactive_analysis(
    llm_input: dict[str, Any],
    mode: str,
    provider: str = "anthropic",
    model: str | None = None,
) -> dict[str, Any]:
    if provider != "anthropic":
        raise ValueError(f"Unsupported provider: {provider}")

    api_key = getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Missing ANTHROPIC_API_KEY.")

    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise ValueError("anthropic package is not installed.") from exc

    chosen_model = model or getenv("POKEPOCKETPEDIA_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    tool_schema = {
        "name": "submit_interactive_analysis",
        "description": "Submit structured interactive deck analysis.",
        "input_schema": {
            "type": "object",
            "required": [
                "executive_summary",
                "composition_assessment",
                "consistency_assessment",
                "meta_matchups",
                "alternatives_and_risks",
                "recommended_additions",
                "confidence_and_limitations",
            ],
            "properties": {
                "executive_summary": {"type": "string"},
                "composition_assessment": {"type": "string"},
                "consistency_assessment": {"type": "string"},
                "meta_matchups": {"type": "string"},
                "alternatives_and_risks": {"type": "array", "items": {"type": "string"}},
                "completion_plan": {"type": "string"},
                "recommended_additions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["card_name", "count", "reason"],
                        "properties": {
                            "card_name": {"type": "string"},
                            "count": {"type": "integer"},
                            "reason": {"type": "string"},
                        },
                    },
                },
                "confidence_and_limitations": {"type": "string"},
            },
        },
    }

    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model=chosen_model,
        max_tokens=1500,
        temperature=0.2,
        system=_system_prompt(mode),
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": "submit_interactive_analysis"},
        messages=[{"role": "user", "content": json.dumps(llm_input, ensure_ascii=True)}],
    )

    raw_text = _extract_text_content(message)
    tool_payload = _extract_tool_input(message)
    payload = tool_payload or _parse_json_response(raw_text)
    normalized = _normalize_output(payload, mode=mode)
    usage = getattr(message, "usage", None)
    return {
        "provider": provider,
        "model": chosen_model,
        "generated_at": _utc_now_iso(),
        "raw_text": raw_text,
        "output": normalized,
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
            "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
        },
    }


def generate_interactive_chat_reply(
    context_input: dict[str, Any],
    mode: str,
    history: list[dict[str, Any]],
    user_message: str,
    provider: str = "anthropic",
    model: str | None = None,
) -> dict[str, Any]:
    if provider != "anthropic":
        raise ValueError(f"Unsupported provider: {provider}")

    api_key = getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Missing ANTHROPIC_API_KEY.")

    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise ValueError("anthropic package is not installed.") from exc

    chosen_model = model or getenv(
        "POKEPOCKETPEDIA_ANTHROPIC_MODEL",
        "claude-sonnet-4-5-20250929",
    )
    client = Anthropic(api_key=api_key)
    messages: list[dict[str, str]] = [
        {
            "role": "user",
            "content": (
                "Context JSON (fixed for this chat):\n"
                f"{json.dumps(context_input, ensure_ascii=True)}\n\n"
                "Use this context for all follow-up answers."
            ),
        }
    ]
    for item in history[-8:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        content = str(item.get("content") or "").strip()
        if role not in {"assistant", "user"} or not content:
            continue
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    message = client.messages.create(
        model=chosen_model,
        max_tokens=900,
        temperature=0.2,
        system=(
            f"{_system_prompt(mode)} "
            "For chat follow-ups, answer clearly and concisely. "
            "Do not invent facts outside provided context."
        ),
        messages=messages,
    )
    usage = getattr(message, "usage", None)
    return {
        "provider": provider,
        "model": chosen_model,
        "generated_at": _utc_now_iso(),
        "reply": _extract_text_content(message),
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
            "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
        },
    }
