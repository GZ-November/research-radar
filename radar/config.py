"""Typed application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        env_file=".env",
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
