"""Service interfaces for every external data provider.

Rules of the road for this package:

1. NOTHING outside `app.services` may talk to an external API. The pipeline and
   the API layer depend only on these Protocols.
2. Every provider ships a mock implementation so the whole pipeline runs offline
   with no keys set.
3. Real implementations are selected in `app.services.registry` based on which
   credentials are configured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.domain import Bar, Direction


class ServiceNotWired(RuntimeError):
    """Raised by a real provider that has not been implemented yet.

    The scaffold ships mocks for every provider; real clients land in the
    "real API wiring" milestone. Raising loudly beats silently returning
    empty data and making the pipeline look broken.
    """


@dataclass(frozen=True, slots=True)
class NewsItem:
    ticker: str
    headline: str
    body: str
    published_at: datetime
    url: str | None = None


@dataclass(frozen=True, slots=True)
class OptionsFlowEvent:
    ticker: str
    premium_usd: float
    direction: Direction
    contract: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class InsiderTransaction:
    ticker: str
    insider_name: str
    is_purchase: bool
    value_usd: float
    filed_at: datetime


@dataclass(frozen=True, slots=True)
class EarningsSurprise:
    ticker: str
    period: str
    eps_actual: float
    eps_estimate: float
    reported_at: datetime

    @property
    def surprise_pct(self) -> float:
        if self.eps_estimate == 0:
            return 0.0
        return (self.eps_actual - self.eps_estimate) / abs(self.eps_estimate) * 100.0


@dataclass(frozen=True, slots=True)
class MaterialityScore:
    """0..1 materiality plus the direction the text implies."""

    score: float
    direction: Direction
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class OrderRequest:
    ticker: str
    side: str          # "buy" | "sell"
    quantity: float
    client_tag: str = ""


@dataclass(frozen=True, slots=True)
class OrderReceipt:
    accepted: bool
    broker_order_id: str
    detail: str = ""
    submitted_payload: dict = field(default_factory=dict)


@runtime_checkable
class MarketDataService(Protocol):
    """Price/volume bars and company news (Alpaca in production)."""

    async def get_bars(self, ticker: str, limit: int) -> list[Bar]: ...

    async def get_news(self, ticker: str, since: datetime) -> list[NewsItem]: ...


@runtime_checkable
class OptionsFlowService(Protocol):
    """Unusual options activity and insider filings (Unusual Whales)."""

    async def get_unusual_flow(
        self, ticker: str, since: datetime
    ) -> list[OptionsFlowEvent]: ...

    async def get_insider_transactions(
        self, ticker: str, since: datetime
    ) -> list[InsiderTransaction]: ...


@runtime_checkable
class FundamentalsService(Protocol):
    """Earnings surprises and calendar (Finnhub)."""

    async def get_earnings_surprises(
        self, ticker: str, since: datetime
    ) -> list[EarningsSurprise]: ...


@runtime_checkable
class FilingsService(Protocol):
    """Free SEC EDGAR backstop for Form 4 insider filings."""

    async def get_form4(
        self, ticker: str, since: datetime
    ) -> list[InsiderTransaction]: ...


@runtime_checkable
class MaterialityScorer(Protocol):
    """Scores TEXT catalysts only (8-K, press release, transcript).

    Numeric catalysts -- EPS surprise %, insider $ value, options premium --
    never reach this interface; they carry their own magnitude.
    """

    async def score(self, ticker: str, text: str) -> MaterialityScore: ...


@runtime_checkable
class ExecutionService(Protocol):
    """Phase-2 placeholder. Paper-trading mock only.

    Deliberately NOT wired to a live broker. Confluence does not place
    discretionary trades; any future execution must be user-preconfigured rules
    routed through a licensed broker.
    """

    async def submit(self, order: OrderRequest) -> OrderReceipt: ...
