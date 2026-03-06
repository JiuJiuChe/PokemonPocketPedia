from __future__ import annotations

from os import getenv

OPENCLAW_PROVIDER = "openclaw"
ANTHROPIC_PROVIDER = "anthropic"

DEFAULT_OPENCLAW_MODEL = "openai-codex/gpt-5.3-codex"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"


def normalize_provider(provider: str | None, default: str = ANTHROPIC_PROVIDER) -> str:
    value = str(provider or "").strip().casefold()
    return value or default


def require_supported_provider(provider: str, allowed: tuple[str, ...]) -> str:
    normalized = normalize_provider(provider)
    if normalized not in allowed:
        raise ValueError(f"Unsupported provider: {provider}")
    return normalized


def resolve_provider_model(
    provider: str,
    explicit_model: str | None,
    *,
    openclaw_env_key: str = "POKEPOCKETPEDIA_OPENCLAW_MODEL",
    openclaw_default: str = DEFAULT_OPENCLAW_MODEL,
    anthropic_env_key: str = "POKEPOCKETPEDIA_ANTHROPIC_MODEL",
    anthropic_default: str = DEFAULT_ANTHROPIC_MODEL,
) -> str:
    if explicit_model and str(explicit_model).strip():
        return str(explicit_model).strip()

    normalized = normalize_provider(provider)
    if normalized == OPENCLAW_PROVIDER:
        return str(getenv(openclaw_env_key, openclaw_default) or openclaw_default).strip()
    if normalized == ANTHROPIC_PROVIDER:
        return str(getenv(anthropic_env_key, anthropic_default) or anthropic_default).strip()
    raise ValueError(f"Unsupported provider: {provider}")


def model_from_env(provider: str) -> str | None:
    normalized = normalize_provider(provider)
    key = "POKEPOCKETPEDIA_OPENCLAW_MODEL" if normalized == OPENCLAW_PROVIDER else "POKEPOCKETPEDIA_ANTHROPIC_MODEL"
    value = str(getenv(key, "") or "").strip()
    return value or None
