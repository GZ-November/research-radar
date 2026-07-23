"""Single entry point for building the analysis LLM from settings.

Every service that needs a structured-output model goes through here so the
local-first policy (``LOCAL_LLM_MODEL`` beats any remote provider) is decided
in exactly one place.
"""

from radar.config import Settings, get_settings
from radar.llm.base import LLMClient
from radar.llm.ollama import OllamaLLMClient
from radar.llm.provider import ProviderLLMClient


# Remote structured-output calls are only usable with all three settings.
REMOTE_REQUIRED_FIELDS = {
    "llm_api_key": "LLM_API_KEY",
    "llm_model": "LLM_MODEL",
    "llm_base_url": "LLM_BASE_URL",
}


def build_analysis_llm(
    settings: Settings | None = None, *, timeout_seconds: float | None = None
) -> LLMClient | None:
    """Build the configured analysis LLM: local Ollama first, remote second.

    Returns None when neither a local model nor the complete remote triple
    (API key, model, base URL) is configured, so callers can gate actions
    instead of failing on the first network call. ``timeout_seconds`` only
    applies to the remote provider client.
    """

    settings = settings or get_settings()
    if settings.local_llm_model:
        return OllamaLLMClient(settings)
    if all(getattr(settings, field) for field in REMOTE_REQUIRED_FIELDS):
        return ProviderLLMClient(settings, timeout_seconds=timeout_seconds)
    return None


def describe_llm_setup(settings: Settings | None = None) -> dict:
    """Describe the active analysis-LLM configuration for UI guidance.

    Returns ``{"configured", "mode", "model", "missing", "provider", "base_url"}``
    where ``mode`` is "local", "remote" or None. Local Ollama remains the
    documented privacy-first override and therefore wins over remote settings.
    """

    settings = settings or get_settings()
    if settings.local_llm_model:
        return {
            "configured": True,
            "mode": "local",
            "model": settings.local_llm_model,
            "provider": "ollama",
            "base_url": settings.local_llm_base_url,
            "missing": [],
        }
    missing = [
        env_name
        for field, env_name in REMOTE_REQUIRED_FIELDS.items()
        if not getattr(settings, field)
    ]
    configured = len(missing) == 0
    return {
        "configured": configured,
        "mode": "remote" if configured else None,
        "model": settings.llm_model if configured else None,
        "provider": settings.llm_provider or "",
        "base_url": settings.llm_base_url or "",
        "missing": missing,
    }
