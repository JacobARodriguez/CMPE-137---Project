"""Deterministic mock providers.

Same ticker in, same data out -- no randomness across runs, so tests can assert
on exact behaviour and a demo is reproducible.

Bar generation lives in `app.services._series`; see that module for the shape
of the synthetic series and why it is built the way it is.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain import Bar, Direction
from app.services._series import (
    breaks_out,
    generate_bars,
    mock_direction,
    seed_of as _seed,
)
from app.services.base import (
    EarningsSurprise,
    InsiderTransaction,
    MaterialityScore,
    NewsItem,
    OptionsFlowEvent,
    OrderReceipt,
    OrderRequest,
)


class MockMarketData:
    """Stands in for Alpaca."""

    async def get_bars(self, ticker: str, limit: int) -> list[Bar]:
        return generate_bars(ticker, limit)

    async def get_news(self, ticker: str, since: datetime) -> list[NewsItem]:
        seed = _seed(ticker)
        if seed % 3 != 0:
            return []
        bullish = mock_direction(ticker) is Direction.BULLISH
        if bullish:
            headline = f"{ticker} announces expanded buyback and raises full-year guidance"
        else:
            headline = f"{ticker} withdraws guidance amid softening demand"
        return [
            NewsItem(
                ticker=ticker,
                headline=headline,
                body=(
                    f"{ticker} disclosed material developments in an 8-K filed "
                    "with the SEC. Management characterised the impact as "
                    "significant to full-year results."
                ),
                published_at=datetime.now(timezone.utc) - timedelta(minutes=5),
                url=f"https://example.invalid/news/{ticker.lower()}",
            )
        ]


class MockOptionsFlow:
    """Stands in for Unusual Whales."""

    async def get_unusual_flow(self, ticker: str, since: datetime) -> list[OptionsFlowEvent]:
        seed = _seed(ticker)
        if seed % 2 != 0:
            return []
        direction = mock_direction(ticker)
        side = "C" if direction is Direction.BULLISH else "P"
        return [
            OptionsFlowEvent(
                ticker=ticker,
                premium_usd=float(250_000 + seed % 750_000),
                direction=direction,
                contract=f"{ticker} {side}",
                observed_at=datetime.now(timezone.utc) - timedelta(minutes=3),
            )
        ]

    async def get_insider_transactions(
        self, ticker: str, since: datetime
    ) -> list[InsiderTransaction]:
        seed = _seed(ticker)
        if seed % 5 != 0:
            return []
        return [
            InsiderTransaction(
                ticker=ticker,
                insider_name="J. Officer",
                is_purchase=mock_direction(ticker) is Direction.BULLISH,
                value_usd=float(120_000 + seed % 2_000_000),
                filed_at=datetime.now(timezone.utc) - timedelta(hours=2),
            )
        ]


class MockFundamentals:
    """Stands in for Finnhub."""

    async def get_earnings_surprises(
        self, ticker: str, since: datetime
    ) -> list[EarningsSurprise]:
        seed = _seed(ticker)
        if seed % 4 != 0:
            return []
        estimate = 1.00 + (seed % 50) / 100.0
        beat = mock_direction(ticker) is Direction.BULLISH
        actual = estimate * (1.12 if beat else 0.88)
        return [
            EarningsSurprise(
                ticker=ticker,
                period="Q3",
                eps_actual=round(actual, 4),
                eps_estimate=round(estimate, 4),
                reported_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            )
        ]


class MockFilings:
    """Stands in for SEC EDGAR Form 4."""

    async def get_form4(self, ticker: str, since: datetime) -> list[InsiderTransaction]:
        seed = _seed(ticker)
        if seed % 7 != 0:
            return []
        return [
            InsiderTransaction(
                ticker=ticker,
                insider_name="A. Director",
                is_purchase=True,
                value_usd=float(80_000 + seed % 400_000),
                filed_at=datetime.now(timezone.utc) - timedelta(hours=6),
            )
        ]


# Keyword tables for the offline materiality heuristic. Not a model -- just a
# transparent, deterministic stand-in so the pipeline runs with no keys.
_BULLISH_TERMS = (
    "raises", "raised", "beat", "buyback", "expanded", "record", "upgrade",
    "accelerating", "approval", "awarded",
)
_BEARISH_TERMS = (
    "withdraws", "cuts", "miss", "investigation", "recall", "downgrade",
    "resign", "delay", "impairment", "softening",
)
_MATERIAL_TERMS = (
    "guidance", "8-k", "material", "sec", "merger", "acquisition", "restate",
    "bankruptcy", "dividend", "full-year",
)


class MockMaterialityScorer:
    """Keyword heuristic standing in for FinBERT / an LLM call."""

    async def score(self, ticker: str, text: str) -> MaterialityScore:
        lowered = text.lower()
        bull = sum(term in lowered for term in _BULLISH_TERMS)
        bear = sum(term in lowered for term in _BEARISH_TERMS)
        material = sum(term in lowered for term in _MATERIAL_TERMS)

        direction = Direction.BEARISH if bear > bull else Direction.BULLISH
        # Saturating score so long documents cannot run away with it.
        raw = (material * 0.18) + (max(bull, bear) * 0.14)
        return MaterialityScore(
            score=round(min(raw, 1.0), 4),
            direction=direction,
            rationale=(
                f"heuristic: {material} materiality term(s), "
                f"{bull} bullish / {bear} bearish term(s)"
            ),
        )


class PaperExecutionService:
    """Paper-trading mock. Records intent; never reaches a broker.

    Execution is explicitly out of MVP scope. This exists so the interface is
    stable for phase 2, and so nothing in the codebase is tempted to grow a
    real order path by accident.
    """

    def __init__(self) -> None:
        self.submitted: list[OrderRequest] = []

    async def submit(self, order: OrderRequest) -> OrderReceipt:
        self.submitted.append(order)
        return OrderReceipt(
            accepted=True,
            broker_order_id=f"paper-{len(self.submitted):06d}",
            detail="Paper trade recorded. No broker was contacted.",
            submitted_payload={
                "ticker": order.ticker,
                "side": order.side,
                "quantity": order.quantity,
            },
        )
