"""Interactive LLM analysis for custom deck evaluation/completion."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from os import getenv
from pathlib import Path
from typing import Any
from uuid import uuid4

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


def _extract_chat_reply(message: Any) -> str:
    raw_text = _extract_text_content(message)
    if raw_text:
        return raw_text

    tool_payload = _extract_tool_input(message)
    if not isinstance(tool_payload, dict):
        return ""

    for key in ("reply", "text", "message", "answer", "result"):
        value = tool_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _extract_tool_input(message: Any, preferred_tool_name: str | None = None) -> dict[str, Any] | None:
    content = getattr(message, "content", [])
    fallback_payload: dict[str, Any] | None = None
    for block in content:
        if getattr(block, "type", None) != "tool_use":
            continue
        payload = getattr(block, "input", None)
        if not isinstance(payload, dict):
            continue
        name = str(getattr(block, "name", "") or "").strip()
        if preferred_tool_name and name == preferred_tool_name:
            return payload
        if fallback_payload is None:
            fallback_payload = payload
    return fallback_payload


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


def _build_openclaw_analysis_message(llm_input: dict[str, Any], mode: str) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    skill_path = repo_root / "skill" / "tcgp-meta-analyst" / "SKILL.md"
    skill_text = ""
    try:
        skill_text = skill_path.read_text(encoding="utf-8")
    except Exception:
        skill_text = ""

    schema_hint = {
        "executive_summary": "string",
        "composition_assessment": "string",
        "consistency_assessment": "string",
        "meta_matchups": "string",
        "alternatives_and_risks": ["string"],
        "completion_plan": "string",
        "recommended_additions": [
            {"card_name": "string", "count": 1, "reason": "string"}
        ],
        "confidence_and_limitations": "string",
    }

    return (
        "You are running as an OpenClaw local analyst for Pokemon Pocket.\n"
        "Read and follow this skill content first:\n"
        f"SKILL_PATH: {skill_path}\n"
        "SKILL_CONTENT_BEGIN\n"
        f"{skill_text}\n"
        "SKILL_CONTENT_END\n\n"
        f"Mode: {mode}.\n"
        "Then analyze the provided context and return ONLY valid JSON object with keys exactly matching this schema hint.\n"
        f"SCHEMA_HINT={json.dumps(schema_hint, ensure_ascii=True)}\n"
        f"LLM_INPUT={json.dumps(llm_input, ensure_ascii=True)}\n"
        "Output must be pure JSON, no markdown, no extra text."
    )


def _extract_openclaw_text(stdout: str) -> str:
    payload_text = ""
    response_obj = json.loads(stdout) if stdout else {}
    payloads = response_obj.get("payloads", []) if isinstance(response_obj, dict) else []
    if payloads and isinstance(payloads[0], dict):
        payload_text = str(payloads[0].get("text") or "").strip()
    if not payload_text and isinstance(response_obj, dict):
        payload_text = str(response_obj.get("text") or "").strip()
    return payload_text


def _run_openclaw_message(message_text: str) -> str:
    timeout_seconds = int(getenv("POKEPOCKETPEDIA_OPENCLAW_TIMEOUT_SECONDS", "600"))
    agent_id = getenv("POKEPOCKETPEDIA_OPENCLAW_AGENT", "main")
    session_id = f"pokepocketpedia-interactive-{uuid4().hex[:10]}"

    cmd = [
        "openclaw",
        "agent",
        "--local",
        "--agent",
        agent_id,
        "--session-id",
        session_id,
        "--timeout",
        str(timeout_seconds),
        "--json",
        "--message",
        message_text,
    ]

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 30,
        )
        if proc.returncode != 0:
            raise ValueError(
                f"openclaw agent failed with code {proc.returncode}: {proc.stderr.strip()}"
            )
        return _extract_openclaw_text(proc.stdout.strip())
    except Exception as exc:
        raise ValueError(f"OpenClaw invocation failed: {exc}") from exc


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
    if provider == "openclaw":
        raw_text = _run_openclaw_message(_build_openclaw_analysis_message(llm_input, mode))
        payload = _parse_json_response(raw_text)
        normalized = _normalize_output(payload, mode=mode)
        if payload is None:
            normalized["confidence_and_limitations"] = (
                f"{normalized.get('confidence_and_limitations', '').strip()} OpenClaw note: Non-JSON output received."
            ).strip()
        return {
            "provider": "openclaw",
            "model": model or getenv("POKEPOCKETPEDIA_OPENCLAW_MODEL", "openai-codex/gpt-5.3-codex"),
            "generated_at": _utc_now_iso(),
            "raw_text": raw_text,
            "output": normalized,
            "usage": {"input_tokens": None, "output_tokens": None},
        }
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
    try:
        message = client.beta.messages.create(
            model=chosen_model,
            max_tokens=4096,
            temperature=0.2,
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
            system=_system_prompt(mode),
            tools=[_CODE_EXECUTION_TOOL, tool_schema],
            messages=[{"role": "user", "content": json.dumps(llm_input, ensure_ascii=True)}],
        )
    except Exception as exc:  # pragma: no cover - network/provider error path
        raise ValueError(f"Anthropic request failed: {exc}") from exc

    raw_text = _extract_text_content(message)
    tool_payload = _extract_tool_input(
        message,
        preferred_tool_name="submit_interactive_analysis",
    )
    payload = tool_payload or _parse_json_response(raw_text)
    normalized = _normalize_output(payload, mode=mode)
    usage = getattr(message, "usage", None)
    result: dict[str, Any] = {
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
    if _debug_enabled():
        result["debug"] = _build_debug_payload(message, raw_text)
    return result


def generate_interactive_chat_reply(
    context_input: dict[str, Any],
    mode: str,
    history: list[dict[str, Any]],
    user_message: str,
    provider: str = "anthropic",
    model: str | None = None,
) -> dict[str, Any]:
    if provider == "openclaw":
        history_rows: list[str] = []
        for item in history[-8:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip()
            content = str(item.get("content") or "").strip()
            if role in {"assistant", "user"} and content:
                history_rows.append(f"{role}: {content}")

        prompt = (
            "You are running as an OpenClaw local analyst for Pokemon Pocket. "
            "Answer the user question based only on the provided context.\n"
            f"MODE={mode}\n"
            f"CONTEXT={json.dumps(context_input, ensure_ascii=True)}\n"
            f"HISTORY={json.dumps(history_rows, ensure_ascii=True)}\n"
            f"USER_MESSAGE={user_message}\n"
            "Return plain text answer only."
        )
        reply = _run_openclaw_message(prompt)
        return {
            "provider": "openclaw",
            "model": model or getenv("POKEPOCKETPEDIA_OPENCLAW_MODEL", "openai-codex/gpt-5.3-codex"),
            "generated_at": _utc_now_iso(),
            "reply": reply,
            "usage": {"input_tokens": None, "output_tokens": None},
        }
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

    try:
        message = client.beta.messages.create(
            model=chosen_model,
            max_tokens=4096,
            temperature=0.2,
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
            tools=[_CODE_EXECUTION_TOOL],
            system=(
                f"{_system_prompt(mode)} "
                "For chat follow-ups, answer clearly and concisely. "
                "Do not invent facts outside provided context."
            ),
            messages=messages,
        )
    except Exception as exc:  # pragma: no cover - network/provider error path
        raise ValueError(f"Anthropic request failed: {exc}") from exc
    usage = getattr(message, "usage", None)
    raw_text = _extract_chat_reply(message)
    result: dict[str, Any] = {
        "provider": provider,
        "model": chosen_model,
        "generated_at": _utc_now_iso(),
        "reply": raw_text,
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
            "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
        },
    }
    if _debug_enabled():
        result["debug"] = _build_debug_payload(message, raw_text)
    return result
