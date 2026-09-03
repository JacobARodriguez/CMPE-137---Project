"""Provider selection.

The one place that decides real-vs-mock. Everything else takes services by
injection, which is what makes the pipeline testable and lets the whole system
boot with zero configuration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import MaterialityBackend, Settings, get_settings
from app.services.base import (
    ExecutionService,
    FilingsService,
    FundamentalsService,
    MarketDataService,
    MaterialityScorer,
    OptionsFlowService,
)
from app.services.mocks import (
    MockFilings,
    MockFundamentals,
    MockMarketData,
    MockMaterialityScorer,
    MockOptionsFlow,
    PaperExecutionService,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ServiceBundle:
    """Every external dependency the pipeline needs, resolved once."""

    market_data: MarketDataService
    options_flow: OptionsFlowService
    fundamentals: FundamentalsService
    filings: FilingsService
    materiality: MaterialityScorer
    execution: ExecutionService

    # Human-readable record of what got selected, surfaced at /health so it is
    # never a mystery whether you are looking at real or fake data.
    selection: dict[str, str]


def _build_materiality(settings: Settings) -> tuple[MaterialityScorer, str]:
    backend = settings.materiality_backend
    if backend is MaterialityBackend.CLAUDE:
        try:
            from app.services.materiality import ClaudeMaterialityScorer

            return ClaudeMaterialityScorer(settings.anthropic_api_key), "claude"
        except Exception:  # noqa: BLE001 - missing dep or bad credentials
            logger.exception("Claude scorer unavailable; falling back to heuristic")
    elif backend is MaterialityBackend.FINBERT:
        try:
            from app.services.materiality import FinBertMaterialityScorer

            return FinBertMaterialityScorer(), "finbert"
        except Exception:  # noqa: BLE001 - transformers/torch not installed
            logger.exception("FinBERT scorer unavailable; falling back to heuristic")
    return MockMaterialityScorer(), "mock"


def build_services(settings: Settings | None = None) -> ServiceBundle:
    """Resolve the provider set implied by the current configuration."""
    settings = settings or get_settings()
    selection: dict[str, str] = {}

    if settings.use_mock_market_data:
        market_data: MarketDataService = MockMarketData()
        selection["market_data"] = "mock"
    else:
        from app.services.real import AlpacaMarketData

        market_data = AlpacaMarketData(
            settings.alpaca_api_key or "", settings.alpaca_api_secret or ""
        )
        selection["market_data"] = "alpaca"

    if settings.use_mock_options_flow:
        options_flow: OptionsFlowService = MockOptionsFlow()
        selection["options_flow"] = "mock"
    else:
        from app.services.real import UnusualWhalesOptionsFlow

        options_flow = UnusualWhalesOptionsFlow(settings.unusual_whales_api_key or "")
        selection["options_flow"] = "unusual_whales"

    if settings.use_mock_fundamentals:
        fundamentals: FundamentalsService = MockFundamentals()
        selection["fundamentals"] = "mock"
    else:
        from app.services.real import FinnhubFundamentals

        fundamentals = FinnhubFundamentals(settings.finnhub_api_key or "")
        selection["fundamentals"] = "finnhub"

    if settings.use_mock_filings:
        filings: FilingsService = MockFilings()
        selection["filings"] = "mock"
    else:
        from app.services.real import SecEdgarFilings

        filings = SecEdgarFilings(settings.sec_edgar_user_agent)
        selection["filings"] = "sec_edgar"

    materiality, materiality_name = _build_materiality(settings)
    selection["materiality"] = materiality_name

    # Always the paper mock. Live execution is out of scope by design.
    selection["execution"] = "paper_mock"

    return ServiceBundle(
        market_data=market_data,
        options_flow=options_flow,
        fundamentals=fundamentals,
        filings=filings,
        materiality=materiality,
        execution=PaperExecutionService(),
        selection=selection,
    )
