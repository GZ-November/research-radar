"""Typed application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Config layering: the project .env ships with the repo (advanced users), while
# data/settings.local.env is written by the in-app settings page and wins.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
LOCAL_SETTINGS_FILE = PROJECT_ROOT / "data" / "settings.local.env"


# USD per one million tokens: (input, output).
MODEL_TOKEN_PRICES_USD: dict[str, tuple[float, float]] = {
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
}


def estimate_llm_cost_usd(
    model: str | None, input_tokens: int, output_tokens: int
) -> float:
    """Estimate the USD cost of a model run from token usage.

    Unknown models return 0.0; their token counts are still recorded so the
    ledger keeps usage even without a known price.
    """

    prices = MODEL_TOKEN_PRICES_USD.get((model or "").strip().lower())
    if prices is None:
        return 0.0
    input_price, output_price = prices
    return round(
        (input_tokens * input_price + output_tokens * output_price) / 1_000_000, 6
    )


class Settings(BaseSettings):
    """Runtime settings for the local Research Radar application."""

    model_config = SettingsConfigDict(
        # Later files override earlier ones, so the UI-written local file wins.
        env_file=(DEFAULT_ENV_FILE, LOCAL_SETTINGS_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///data/research_radar.db"

    llm_provider: str | None = None
    llm_api_key: str | None = Field(default=None, repr=False)
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_thinking: Literal["enabled", "disabled"] = "enabled"
    llm_reasoning_effort: Literal["high", "max"] = "high"
    llm_max_tokens: int = Field(default=4096, ge=256, le=384_000)
    llm_timeout_seconds: float = Field(default=120.0, ge=15.0, le=900.0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_retry_backoff_seconds: float = Field(default=2.0, ge=0.0, le=60.0)
    llm_manuscript_timeout_seconds: float = Field(default=240.0, ge=45.0, le=900.0)

    # Private local reasoning model used by the live radar before any remote LLM.
    local_llm_model: str | None = None
    local_llm_base_url: str = "http://127.0.0.1:11434"
    local_llm_timeout_seconds: float = Field(default=300.0, ge=30.0, le=1800.0)

    embedding_provider: str | None = None
    embedding_api_key: str | None = Field(default=None, repr=False)
    embedding_model: str | None = None
    embedding_base_url: str | None = None
    embedding_timeout_seconds: float = Field(default=60.0, ge=5.0, le=600.0)
    embedding_max_retries: int = Field(default=3, ge=0, le=5)

    data_dir: Path = Path("data")
    fixture_case_dir: Path = Path("tests/fixtures/golden_case")

    # Contact address sent with Crossref API requests (politeness pool).
    crossref_mailto: str = "local@example.invalid"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one validated settings object per process."""
    return Settings()


def _format_env_value(value: str) -> str:
    """Quote a dotenv value only when it could break simple KEY=VALUE parsing."""

    if value and value.strip() == value and "#" not in value and '"' not in value:
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def save_local_settings(
    updates: dict[str, str], path: Path | None = None
) -> Path:
    """Write UI-edited settings into the local override env file.

    Only ``data/settings.local.env`` is touched (or ``path`` in tests); the
    project ``.env`` is never modified. Lines for keys not present in
    ``updates`` — including comments — are preserved, an empty value writes
    ``KEY=`` which the settings layer treats as unset. The cached settings
    object is cleared so the next ``get_settings()`` call picks the changes up.
    """

    target = path or LOCAL_SETTINGS_FILE
    lines = (
        target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    )
    remaining = {key.strip().upper(): value for key, value in updates.items()}
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip().upper()
            if key in remaining:
                output.append(f"{key}={_format_env_value(remaining.pop(key))}")
                continue
        output.append(line)
    output.extend(
        f"{key}={_format_env_value(value)}" for key, value in remaining.items()
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(output) + "\n", encoding="utf-8")
    get_settings.cache_clear()
    return target


def mask_secret(value: str | None, *, visible_tail: int = 4) -> str:
    """Mask an API key for display, keeping a recognizable prefix and the tail."""

    if not value:
        return ""
    if len(value) <= visible_tail:
        return "•" * 4
    prefix = "sk-" if value.startswith("sk-") else ""
    return f"{prefix}{'•' * 4}{value[-visible_tail:]}"
