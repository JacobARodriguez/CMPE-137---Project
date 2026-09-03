"""Core domain vocabulary shared by the pipeline, the API, and the tests.

These are transport/logic types. Persistence models live in `app.db.models`;
they are kept separate so pipeline logic stays testable without a database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"

    @property
    def opposite(self) -> "Direction":
        return Direction.BEARISH if self is Direction.BULLISH else Direction.BULLISH


class CatalystType(str, Enum):
    EARNINGS_SURPRISE = "earnings_surprise"
    INSIDER_BUY = "insider_buy"
    INSIDER_SELL = "insider_sell"
    OPTIONS_FLOW = "options_flow"
    FILING_8K = "filing_8k"
    NEWS = "news"

    @property
    def is_text_catalyst(self) -> bool:
        """Text catalysts get a materiality score; numeric ones skip that step."""
        return self in {CatalystType.FILING_8K, CatalystType.NEWS}


class CatalystSource(str, Enum):
    ALPACA = "alpaca"
    UNUSUAL_WHALES = "unusual_whales"
    FINNHUB = "finnhub"
    SEC_EDGAR = "sec_edgar"


class RuleType(str, Enum):
    ORB = "orb"
    EMA_CROSS = "ema_cross"
    VOLUME_SPIKE = "volume_spike"
    VWAP_RECLAIM = "vwap_reclaim"


class Combinator(str, Enum):
    AND = "and"
    OR = "or"


class AlertStatus(str, Enum):
    PENDING = "pending"      # catalyst tagged, confirmation window still open
    CONFIRMED = "confirmed"  # a technical rule confirmed it in-window
    EXPIRED = "expired"      # window closed with no confirmation


# How long a catalyst stays eligible for technical confirmation. Options and
# earnings reactions resolve fast; insider filings play out over days.
WINDOW_DURATIONS: dict[CatalystType, timedelta] = {
    CatalystType.OPTIONS_FLOW: timedelta(minutes=30),
    CatalystType.EARNINGS_SURPRISE: timedelta(minutes=60),
    CatalystType.NEWS: timedelta(minutes=90),
    CatalystType.FILING_8K: timedelta(minutes=120),
    CatalystType.INSIDER_BUY: timedelta(hours=24),
    CatalystType.INSIDER_SELL: timedelta(hours=24),
}


@dataclass(frozen=True, slots=True)
class Bar:
    """One OHLCV price bar. `ts` is the bar's OPEN time, in UTC."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True)
class Catalyst:
    """A fundamental event that may precede a tradable move."""

    ticker: str
    type: CatalystType
    source: CatalystSource
    direction: Direction
    magnitude: float           # normalised 0..1 strength of the raw event
    detected_at: datetime
    window_expires_at: datetime
    headline: str
    materiality: float | None = None  # only set for text catalysts
    payload: dict = field(default_factory=dict)
    id: str | None = None

    def expired(self, now: datetime | None = None) -> bool:
        return (now or utcnow()) >= self.window_expires_at


@dataclass(frozen=True, slots=True)
class RuleSpec:
    """One configured technical rule inside a rule set."""

    type: RuleType
    params: dict = field(default_factory=dict)
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class RuleSet:
    """A user's named bundle of technical rules."""

    name: str
    combinator: Combinator
    rules: tuple[RuleSpec, ...]
    id: int | None = None
    user_id: int | None = None

    def fingerprint(self) -> str:
        """Identity for de-duplicating evaluation across users.

        Two users with identical rules must not cause the rule engine to run
        twice for the same ticker -- see `app.pipeline.runner`.
        """
        parts = [self.combinator.value]
        for r in sorted(self.rules, key=lambda r: r.type.value):
            if not r.enabled:
                continue
            params = ",".join(f"{k}={r.params[k]}" for k in sorted(r.params))
            parts.append(f"{r.type.value}({params})")
        return "|".join(parts)


@dataclass(frozen=True, slots=True)
class RuleHit:
    """A single rule that fired, with a human-readable reason."""

    rule_type: RuleType
    direction: Direction
    detail: str


@dataclass(frozen=True, slots=True)
class ConfirmationResult:
    confirmed: bool
    hits: tuple[RuleHit, ...]
    evaluated_at: datetime

    @property
    def rule_tags(self) -> list[str]:
        return [h.rule_type.value for h in self.hits]


@dataclass(slots=True)
class Alert:
    """A ranked, confirmed signal ready to push to a user's dashboard."""

    user_id: int
    ticker: str
    direction: Direction
    confidence: float
    why: str
    catalyst: Catalyst
    confirmation: ConfirmationResult
    rule_set_id: int | None = None
    status: AlertStatus = AlertStatus.CONFIRMED
    created_at: datetime = field(default_factory=utcnow)
    id: int | None = None
