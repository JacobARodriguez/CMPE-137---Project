"""Real provider implementations.

MILESTONE STATUS: not yet wired. The build order in the spec is "mocks first,
real APIs after the pipeline works end-to-end", so these are deliberate,
loud stubs rather than untested network code.

Each class carries the endpoint and auth shape it will need, so wiring one up
is a matter of filling in `_request` and mapping the response -- not rediscovering
the API. `app.services.registry` only selects these when the relevant credentials
are configured, so an unconfigured install never reaches them.

When implementing:
  * keep the return types exactly as the Protocols in `base.py` declare them
  * do all HTTP through `httpx.AsyncClient` with an explicit timeout
  * never raise raw provider errors past this layer -- wrap them
"""

from __future__ import annotations

from datetime import datetime

from app.domain import Bar
from app.services.base import (
    EarningsSurprise,
    InsiderTransaction,
    NewsItem,
    OptionsFlowEvent,
    ServiceNotWired,
)


class AlpacaMarketData:
    """Alpaca market data.

    Bars:  GET https://data.alpaca.markets/v2/stocks/{symbol}/bars
    News:  GET https://data.alpaca.markets/v1beta1/news
    Auth:  APCA-API-KEY-ID / APCA-API-SECRET-KEY headers
    """

    BARS_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    NEWS_URL = "https://data.alpaca.markets/v1beta1/news"

    def __init__(self, api_key: str, api_secret: str) -> None:
        self._api_key = api_key
        self._api_secret = api_secret

    async def get_bars(self, ticker: str, limit: int) -> list[Bar]:
        raise ServiceNotWired(
            "AlpacaMarketData.get_bars is not implemented yet. "
            "Unset ALPACA_API_KEY to fall back to the mock provider."
        )

    async def get_news(self, ticker: str, since: datetime) -> list[NewsItem]:
        raise ServiceNotWired(
            "AlpacaMarketData.get_news is not implemented yet. "
            "Unset ALPACA_API_KEY to fall back to the mock provider."
        )


class UnusualWhalesOptionsFlow:
    """Unusual Whales options flow + insider filings.

    Auth: Authorization: Bearer <token>
    """

    BASE_URL = "https://api.unusualwhales.com/api"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def get_unusual_flow(self, ticker: str, since: datetime) -> list[OptionsFlowEvent]:
        raise ServiceNotWired(
            "UnusualWhalesOptionsFlow.get_unusual_flow is not implemented yet. "
            "Unset UNUSUAL_WHALES_API_KEY to fall back to the mock provider."
        )

    async def get_insider_transactions(
        self, ticker: str, since: datetime
    ) -> list[InsiderTransaction]:
        raise ServiceNotWired(
            "UnusualWhalesOptionsFlow.get_insider_transactions is not implemented yet. "
            "Unset UNUSUAL_WHALES_API_KEY to fall back to the mock provider."
        )


class FinnhubFundamentals:
    """Finnhub earnings surprises and calendar.

    Surprises: GET https://finnhub.io/api/v1/stock/earnings?symbol=...
    Auth:      X-Finnhub-Token header
    """

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def get_earnings_surprises(
        self, ticker: str, since: datetime
    ) -> list[EarningsSurprise]:
        raise ServiceNotWired(
            "FinnhubFundamentals.get_earnings_surprises is not implemented yet. "
            "Unset FINNHUB_API_KEY to fall back to the mock provider."
        )


class SecEdgarFilings:
    """SEC EDGAR Form 4 backstop.

    No API key; SEC requires a descriptive User-Agent on every request and
    rate-limits to ~10 requests/second. Company facts live under
    https://data.sec.gov/ and the full-text search under
    https://efts.sec.gov/LATEST/search-index?q=...
    """

    BASE_URL = "https://data.sec.gov"

    def __init__(self, user_agent: str) -> None:
        self._user_agent = user_agent

    async def get_form4(self, ticker: str, since: datetime) -> list[InsiderTransaction]:
        raise ServiceNotWired(
            "SecEdgarFilings.get_form4 is not implemented yet. "
            "Set SERVICE_MODE=mock to fall back to the mock provider."
        )
