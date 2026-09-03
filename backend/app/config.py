"""Application configuration.

Every external dependency is optional. With no environment configured at all the
app boots on SQLite, an in-memory catalyst-window store, and mock data services,
which is what the offline test suite and `python -m app.demo` exercise.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceMode(str, Enum):
    """How to choose between real and mock provider implementations."""

    AUTO = "auto"  # real when that provider's key is set, mock otherwise
    MOCK = "mock"  # always mock, even if keys are present


class MaterialityBackend(str, Enum):
    MOCK = "mock"
    CLAUDE = "claude"
    FINBERT = "finbert"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Core
    confluence_env: str = "dev"
    # >=32 bytes so HS256 does not warn. Overridden via SECRET_KEY in any
    # real deployment -- see `warn_if_insecure`.
    secret_key: str = "dev-only-insecure-key-not-for-production-use"
    access_token_ttl_minutes: int = 60 * 12
    database_url: str = "sqlite+aiosqlite:///./confluence.db"
    redis_url: str | None = None

    # Pipeline
    poll_interval_seconds: int = 60
    bar_lookback: int = 200

    # Provider selection
    service_mode: ServiceMode = ServiceMode.AUTO

    # Provider credentials
    alpaca_api_key: str | None = None
    alpaca_api_secret: str | None = None
    unusual_whales_api_key: str | None = None
    finnhub_api_key: str | None = None
    sec_edgar_user_agent: str = "Confluence/0.1 (contact@example.com)"
    # SEC EDGAR needs no API key, so there is no credential for SERVICE_MODE=auto
    # to key off. Opt in explicitly once the real client is implemented.
    enable_real_filings: bool = False

    # Materiality scoring
    materiality_backend: MaterialityBackend = MaterialityBackend.MOCK
    anthropic_api_key: str | None = None

    @property
    def use_mock_market_data(self) -> bool:
        return self.service_mode is ServiceMode.MOCK or not (
            self.alpaca_api_key and self.alpaca_api_secret
        )

    @property
    def use_mock_options_flow(self) -> bool:
        return self.service_mode is ServiceMode.MOCK or not self.unusual_whales_api_key

    @property
    def use_mock_fundamentals(self) -> bool:
        return self.service_mode is ServiceMode.MOCK or not self.finnhub_api_key

    @property
    def use_mock_filings(self) -> bool:
        return self.service_mode is ServiceMode.MOCK or not self.enable_real_filings


DEV_SECRET_KEY = "dev-only-insecure-key-not-for-production-use"


def warn_if_insecure(settings: Settings) -> list[str]:
    """Configuration problems that matter outside local development."""
    problems: list[str] = []
    if settings.confluence_env != "dev" and settings.secret_key == DEV_SECRET_KEY:
        problems.append("SECRET_KEY is still the development default")
    if settings.confluence_env != "dev" and settings.database_url.startswith("sqlite"):
        problems.append("DATABASE_URL is SQLite; use PostgreSQL outside dev")
    return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
