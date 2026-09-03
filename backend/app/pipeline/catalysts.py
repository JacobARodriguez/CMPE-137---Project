"""Stages 1-3 of the pipeline: ingest, score materiality, tag the catalyst.

Ingest fans out across every provider for ONE ticker, once. The result is a set
of tagged catalysts, each with a direction, a normalised magnitude, and an open
confirmation window.

Materiality scoring applies to text catalysts only. Numeric catalysts carry
their own magnitude:

    EPS surprise %      -> magnitude from the size of the beat/miss
    insider $ value     -> magnitude from the dollar amount
    options premium $   -> magnitude from the premium
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.domain import (
    WINDOW_DURATIONS,
    Catalyst,
    CatalystSource,
    CatalystType,
    Direction,
    utcnow,
)
from app.services.base import (
    EarningsSurprise,
    InsiderTransaction,
    MaterialityScorer,
    NewsItem,
    OptionsFlowEvent,
)
from app.services.registry import ServiceBundle

logger = logging.getLogger(__name__)

# Saturation points for normalising raw numbers into a 0..1 magnitude. Above
# these, magnitude is 1.0 -- a $10M options sweep is not meaningfully "more
# confirming" than a $2M one for our purposes.
EPS_SURPRISE_SATURATION_PCT = 25.0
INSIDER_VALUE_SATURATION_USD = 2_000_000.0
OPTIONS_PREMIUM_SATURATION_USD = 1_000_000.0

# Text catalysts below this materiality are dropped rather than opening a window.
MIN_MATERIALITY = 0.25


def _saturate(value: float, ceiling: float) -> float:
    if ceiling <= 0:
        return 0.0
    return round(min(abs(value) / ceiling, 1.0), 4)


def _window_for(catalyst_type: CatalystType, start: datetime) -> datetime:
    return start + WINDOW_DURATIONS[catalyst_type]


def catalyst_from_earnings(surprise: EarningsSurprise) -> Catalyst:
    pct = surprise.surprise_pct
    direction = Direction.BULLISH if pct >= 0 else Direction.BEARISH
    now = utcnow()
    return Catalyst(
        ticker=surprise.ticker,
        type=CatalystType.EARNINGS_SURPRISE,
        source=CatalystSource.FINNHUB,
        direction=direction,
        magnitude=_saturate(pct, EPS_SURPRISE_SATURATION_PCT),
        detected_at=now,
        window_expires_at=_window_for(CatalystType.EARNINGS_SURPRISE, now),
        headline=(
            f"{surprise.ticker} {surprise.period} EPS "
            f"{'beat' if pct >= 0 else 'missed'} by {abs(pct):.1f}% "
            f"({surprise.eps_actual:.2f} vs {surprise.eps_estimate:.2f} est)"
        ),
        payload={
            "eps_actual": surprise.eps_actual,
            "eps_estimate": surprise.eps_estimate,
            "surprise_pct": round(pct, 2),
            "period": surprise.period,
        },
    )


def catalyst_from_insider(txn: InsiderTransaction, source: CatalystSource) -> Catalyst:
    catalyst_type = CatalystType.INSIDER_BUY if txn.is_purchase else CatalystType.INSIDER_SELL
    direction = Direction.BULLISH if txn.is_purchase else Direction.BEARISH
    now = utcnow()
    return Catalyst(
        ticker=txn.ticker,
        type=catalyst_type,
        source=source,
        direction=direction,
        magnitude=_saturate(txn.value_usd, INSIDER_VALUE_SATURATION_USD),
        detected_at=now,
        window_expires_at=_window_for(catalyst_type, now),
        headline=(
            f"{txn.insider_name} {'bought' if txn.is_purchase else 'sold'} "
            f"${txn.value_usd:,.0f} of {txn.ticker}"
        ),
        payload={
            "insider_name": txn.insider_name,
            "value_usd": round(txn.value_usd, 2),
            "is_purchase": txn.is_purchase,
        },
    )


def catalyst_from_options_flow(event: OptionsFlowEvent) -> Catalyst:
    now = utcnow()
    return Catalyst(
        ticker=event.ticker,
        type=CatalystType.OPTIONS_FLOW,
        source=CatalystSource.UNUSUAL_WHALES,
        direction=event.direction,
        magnitude=_saturate(event.premium_usd, OPTIONS_PREMIUM_SATURATION_USD),
        detected_at=now,
        window_expires_at=_window_for(CatalystType.OPTIONS_FLOW, now),
        headline=(
            f"${event.premium_usd:,.0f} {event.direction.value} options premium "
            f"in {event.contract}"
        ),
        payload={
            "premium_usd": round(event.premium_usd, 2),
            "contract": event.contract,
        },
    )


async def catalyst_from_news(
    item: NewsItem, scorer: MaterialityScorer
) -> Catalyst | None:
    """Score a text catalyst and tag it, or drop it if immaterial."""
    assessment = await scorer.score(item.ticker, f"{item.headline}\n\n{item.body}")
    if assessment.score < MIN_MATERIALITY:
        logger.debug(
            "Dropping immaterial news for %s (score %.2f)", item.ticker, assessment.score
        )
        return None

    now = utcnow()
    catalyst_type = (
        CatalystType.FILING_8K if "8-k" in item.body.lower() else CatalystType.NEWS
    )
    return Catalyst(
        ticker=item.ticker,
        type=catalyst_type,
        source=CatalystSource.ALPACA,
        direction=assessment.direction,
        magnitude=assessment.score,
        materiality=assessment.score,
        detected_at=now,
        window_expires_at=_window_for(catalyst_type, now),
        headline=item.headline,
        payload={
            "url": item.url,
            "rationale": assessment.rationale,
            "published_at": item.published_at.isoformat(),
        },
    )


async def detect_catalysts(
    ticker: str, services: ServiceBundle, since: datetime
) -> list[Catalyst]:
    """Run every detector for one ticker, once.

    This is called once per ticker per poll and its output is shared across all
    users watching that ticker -- see `app.pipeline.runner`.
    """
    news, flow, insiders, earnings, form4 = await asyncio.gather(
        services.market_data.get_news(ticker, since),
        services.options_flow.get_unusual_flow(ticker, since),
        services.options_flow.get_insider_transactions(ticker, since),
        services.fundamentals.get_earnings_surprises(ticker, since),
        services.filings.get_form4(ticker, since),
        return_exceptions=True,
    )

    def _ok(result, label: str) -> list:
        if isinstance(result, BaseException):
            # One provider failing must not lose the others' catalysts.
            logger.warning("Provider %s failed for %s: %s", label, ticker, result)
            return []
        return result

    catalysts: list[Catalyst] = []

    for surprise in _ok(earnings, "fundamentals"):
        catalysts.append(catalyst_from_earnings(surprise))

    for event in _ok(flow, "options_flow"):
        catalysts.append(catalyst_from_options_flow(event))

    for txn in _ok(insiders, "insider"):
        catalysts.append(catalyst_from_insider(txn, CatalystSource.UNUSUAL_WHALES))

    for txn in _ok(form4, "filings"):
        catalysts.append(catalyst_from_insider(txn, CatalystSource.SEC_EDGAR))

    for item in _ok(news, "news"):
        scored = await catalyst_from_news(item, services.materiality)
        if scored is not None:
            catalysts.append(scored)

    return catalysts
