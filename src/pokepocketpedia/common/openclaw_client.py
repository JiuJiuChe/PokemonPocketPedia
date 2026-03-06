from __future__ import annotations

import json
import subprocess
from os import getenv
from uuid import uuid4


def extract_text_from_openclaw_json(stdout: str) -> str:
    response_obj = json.loads(stdout) if stdout else {}
    payloads = response_obj.get("payloads", []) if isinstance(response_obj, dict) else []
    if payloads and isinstance(payloads[0], dict):
        text = str(payloads[0].get("text") or "").strip()
        if text:
            return text
    if isinstance(response_obj, dict):
        return str(response_obj.get("text") or "").strip()
    return ""


def run_openclaw_message(
    message_text: str,
    *,
    session_prefix: str,
    timeout_seconds: int | None = None,
    agent_id: str | None = None,
) -> str:
    resolved_timeout = timeout_seconds or int(getenv("POKEPOCKETPEDIA_OPENCLAW_TIMEOUT_SECONDS", "600"))
    resolved_agent = agent_id or getenv("POKEPOCKETPEDIA_OPENCLAW_AGENT", "main")
    session_id = f"{session_prefix}-{uuid4().hex[:10]}"

    cmd = [
        "openclaw",
        "agent",
        "--local",
        "--agent",
        resolved_agent,
        "--session-id",
        session_id,
        "--timeout",
        str(resolved_timeout),
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
            timeout=resolved_timeout + 30,
        )
    except Exception as exc:
        raise ValueError(f"OpenClaw invocation failed: {exc}") from exc

    if proc.returncode != 0:
        raise ValueError(
            f"openclaw agent failed with code {proc.returncode}: {proc.stderr.strip()}"
        )

    return extract_text_from_openclaw_json(proc.stdout.strip())
