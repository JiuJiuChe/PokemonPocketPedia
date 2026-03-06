from pokepocketpedia.common import providers


def test_require_supported_provider_normalizes_case() -> None:
    assert providers.require_supported_provider(" OpenClaw ", ("openclaw", "anthropic")) == "openclaw"


def test_resolve_provider_model_prefers_explicit() -> None:
    assert providers.resolve_provider_model("openclaw", "x-model") == "x-model"
