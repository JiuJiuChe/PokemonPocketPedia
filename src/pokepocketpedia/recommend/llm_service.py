"""LLM provider integration for recommendation generation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from os import getenv
from typing import Any

_ANTHROPIC_SKILL_ID = getenv(
    "POKEPOCKETPEDIA_ANTHROPIC_SKILL_ID",
    "skill_01SbQZuyL957HXTJcgwU7ffS",
)
_ANTHROPIC_SKILL_VERSION = getenv("POKEPOCKETPEDIA_ANTHROPIC_SKILL_VERSION", "latest")
_ANTHROPIC_BETAS = ["code-execution-2025-08-25", "skills-2025-10-02"]
_CODE_EXECUTION_TOOL = {"type": "code_execution_20250825", "name": "code_execution"}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _debug_enabled() -> bool:
    raw = str(getenv("POKEPOCKETPEDIA_ANTHROPIC_DEBUG", "")).strip().casefold()
    return raw in {"1", "true", "yes", "on"}


def _build_system_prompt() -> str:
    return (
        "You are a competitive Pokemon TCG Pocket strategy analyst. "
        "Use only the provided JSON context and avoid unsupported assumptions. "
        "Prefer concise, actionable language for ranked ladder play. "
        "For substitute_cards, pick 3 to 5 replacements from context.substitute_candidates only."
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
        input_payload = getattr(block, "input", None)
        if isinstance(input_payload, dict):
            return input_payload
    return None


def _collect_tool_use_names(message: Any) -> list[str]:
    names: list[str] = []
    content = getattr(message, "content", [])
    for block in content:
        if getattr(block, "type", None) != "tool_use":
            continue
        name = str(getattr(block, "name", "") or "").strip()
        if name:
            names.append(name)
    return names


def _build_debug_payload(message: Any, raw_text: str) -> dict[str, Any]:
    content = getattr(message, "content", [])
    content_types = [str(getattr(block, "type", "") or "") for block in content]
    return {
        "skill": {
            "id": _ANTHROPIC_SKILL_ID,
            "version": _ANTHROPIC_SKILL_VERSION,
            "betas": _ANTHROPIC_BETAS,
        },
        "message": {
            "id": getattr(message, "id", None),
            "model": getattr(message, "model", None),
            "stop_reason": getattr(message, "stop_reason", None),
            "stop_sequence": getattr(message, "stop_sequence", None),
            "content_block_types": content_types,
            "tool_use_names": _collect_tool_use_names(message),
        },
        "raw_text": raw_text,
    }


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
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

    return None


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_substitute_list(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, dict):
            replace_card = str(item.get("replace_card") or "").strip()
            add_card = str(item.get("add_card") or "").strip()
            reason = str(item.get("reason") or "").strip()
            expected_impact = str(item.get("expected_impact") or "").strip()
            confidence = str(item.get("confidence") or "").strip()
            if not replace_card or not add_card:
                continue
            out.append(
                {
                    "replace_card": replace_card,
                    "add_card": add_card,
                    "reason": reason,
                    "expected_impact": expected_impact,
                    "confidence": confidence,
                }
            )
        elif isinstance(item, str) and item.strip():
            out.append(
                {
                    "replace_card": "",
                    "add_card": item.strip(),
                    "reason": "",
                    "expected_impact": "",
                    "confidence": "",
                }
            )
    return out


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _fallback_substitutes(llm_input: dict[str, Any]) -> list[dict[str, Any]]:
    context = llm_input.get("context", {}) if isinstance(llm_input, dict) else {}
    candidates = context.get("substitute_candidates", []) if isinstance(context, dict) else []
    if not isinstance(candidates, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        replace_name = str(item.get("replace_card_name") or "").strip()
        add_name = str(item.get("candidate_card_name") or "").strip()
        if not replace_name or not add_name:
            continue
        pair = (replace_name.casefold(), add_name.casefold())
        if pair in seen:
            continue
        seen.add(pair)
        out.append(
            {
                "replace_card": replace_name,
                "add_card": add_name,
                "reason": "High meta usage candidate with compatible slot profile.",
                "expected_impact": "Improves consistency against current popular decks.",
                "confidence": "medium",
            }
        )
        if len(out) >= 5:
            break
    return out


def _default_strategy(llm_input: dict[str, Any], reason: str) -> dict[str, Any]:
    context = llm_input.get("context", {}) if isinstance(llm_input, dict) else {}
    target = context.get("target_deck", {}) if isinstance(context, dict) else {}
    key_cards = context.get("key_cards_from_samples", []) if isinstance(context, dict) else []
    top_card_names = [
        str(item.get("card_name"))
        for item in key_cards[:6]
        if isinstance(item, dict) and item.get("card_name")
    ]
    deck_name = str(target.get("deck_name") or "target deck")
    deck_rank = target.get("rank")
    share_pct = target.get("share_pct")
    deck_label = f"{deck_name} (rank={deck_rank}, share={share_pct}%)"

    return {
        "deck_gameplan": (
            f"Base strategy for {deck_label}: establish board early, protect key evolution lines, "
            "and convert tempo advantages into safe closing turns."
        ),
        "key_cards_and_roles": [
            f"{name}: core inclusion from sampled decklists." for name in top_card_names
        ],
        "opening_plan": "Prioritize setup consistency and avoid risky all-in lines without backup.",
        "midgame_plan": (
            "Trade efficiently, pressure opposing setup pieces, and preserve finishing options."
        ),
        "closing_plan": (
            "Secure win path by sequencing your strongest threat with resource protection."
        ),
        "tech_choices": [
            "Adjust flex slots based on the top opposing archetypes in current meta metrics."
        ],
        "substitute_cards": _fallback_substitutes(llm_input),
        "common_pitfalls": [
            "Overextending resources before confirming opponent's counterplay window."
        ],
        "confidence_and_limitations": (
            "Fallback strategy generated because structured model response was unavailable. "
            f"Reason: {reason}"
        ),
    }


def _normalize_structured_output(
    payload: dict[str, Any] | None,
    llm_input: dict[str, Any],
    raw_text: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _default_strategy(llm_input, "No valid JSON payload returned.")

    out = {
        "deck_gameplan": _normalize_text(payload.get("deck_gameplan")),
        "key_cards_and_roles": _normalize_list(payload.get("key_cards_and_roles")),
        "opening_plan": _normalize_text(payload.get("opening_plan")),
        "midgame_plan": _normalize_text(payload.get("midgame_plan")),
        "closing_plan": _normalize_text(payload.get("closing_plan")),
        "tech_choices": _normalize_list(payload.get("tech_choices")),
        "substitute_cards": _normalize_substitute_list(payload.get("substitute_cards")),
        "common_pitfalls": _normalize_list(payload.get("common_pitfalls")),
        "confidence_and_limitations": _normalize_text(payload.get("confidence_and_limitations")),
    }

    missing = [key for key, value in out.items() if (not value and value != [])]
    if missing:
        fallback = _default_strategy(
            llm_input,
            f"Missing required sections from model response: {', '.join(missing)}",
        )
        for key in missing:
            out[key] = fallback[key]

    if not out["confidence_and_limitations"]:
        out["confidence_and_limitations"] = (
            "Generated from model output with partial normalization. Validate with ladder testing."
        )
    if not out["substitute_cards"]:
        out["substitute_cards"] = _fallback_substitutes(llm_input)
    if raw_text and "non-JSON" in out["confidence_and_limitations"].lower():
        out["confidence_and_limitations"] += " Raw model text was captured for reference."
    return out


def generate_with_anthropic(
    llm_input: dict[str, Any],
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    api_key = getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Missing ANTHROPIC_API_KEY.")

    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise ValueError("anthropic package is not installed.") from exc

    client = Anthropic(api_key=api_key)
    user_payload = {
        "instruction": "Generate strategy guidance using tool output schema only.",
        "input": llm_input,
    }

    tool_schema = {
        "name": "submit_strategy",
        "description": "Submit structured deck strategy analysis.",
        "input_schema": {
            "type": "object",
            "required": [
                "deck_gameplan",
                "key_cards_and_roles",
                "opening_plan",
                "midgame_plan",
                "closing_plan",
                "tech_choices",
                "substitute_cards",
                "common_pitfalls",
                "confidence_and_limitations",
            ],
            "properties": {
                "deck_gameplan": {"type": "string"},
                "key_cards_and_roles": {"type": "array", "items": {"type": "string"}},
                "opening_plan": {"type": "string"},
                "midgame_plan": {"type": "string"},
                "closing_plan": {"type": "string"},
                "tech_choices": {"type": "array", "items": {"type": "string"}},
                "substitute_cards": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["replace_card", "add_card", "reason"],
                        "properties": {
                            "replace_card": {"type": "string"},
                            "add_card": {"type": "string"},
                            "reason": {"type": "string"},
                            "expected_impact": {"type": "string"},
                            "confidence": {"type": "string"},
                        },
                        "additionalProperties": True,
                    },
                },
                "common_pitfalls": {"type": "array", "items": {"type": "string"}},
                "confidence_and_limitations": {"type": "string"},
            },
        },
    }

    try:
        message = client.beta.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            betas=_ANTHROPIC_BETAS,
            container={
                "skills": [
                    {
                        "type": "custom",
                        "skill_id": _ANTHROPIC_SKILL_ID,
                        "version": _ANTHROPIC_SKILL_VERSION,
                    }
                ]
            },
            system=_build_system_prompt(),
            tools=[_CODE_EXECUTION_TOOL, tool_schema],
            tool_choice={"type": "tool", "name": "submit_strategy"},
            messages=[{"role": "user", "content": json.dumps(user_payload, ensure_ascii=True)}],
        )
    except Exception as exc:  # pragma: no cover - network/provider error path
        raise ValueError(f"Anthropic request failed: {exc}") from exc

    raw_text = _extract_text_content(message)
    tool_payload = _extract_tool_input(message)
    structured = _normalize_structured_output(
        payload=tool_payload or _parse_json_response(raw_text),
        llm_input=llm_input,
        raw_text=raw_text,
    )
    usage = getattr(message, "usage", None)
    debug = _build_debug_payload(message, raw_text) if _debug_enabled() else None

    result: dict[str, Any] = {
        "provider": "anthropic",
        "model": model,
        "generated_at": _utc_now_iso(),
        "structured_output": structured,
        "raw_text": raw_text,
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
            "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
        },
    }
    if debug is not None:
        result["debug"] = debug
    return result


def generate_recommendation(
    llm_input: dict[str, Any],
    provider: str = "anthropic",
    model: str | None = None,
) -> dict[str, Any]:
    if provider != "anthropic":
        raise ValueError(f"Unsupported provider: {provider}")

    chosen_model = model or getenv("POKEPOCKETPEDIA_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    return generate_with_anthropic(llm_input=llm_input, model=chosen_model)
