"""Deterministic synthetic bar series used by the mock market-data provider.

Kept in its own module because the exact shape matters: the offline test suite
and the demo both assert on which rules fire, so this generator must be
predictable rather than merely "random-looking".

Two shapes, chosen by a stable hash of the ticker:

* breakout -- a flat base price punctuated by periodic decisive "event" bars
              (a ~1.2% move on ~6x volume). Every event bar confirms; the bars
              between them do not. The final bar is always an event, so live
              confirmation has something to find, and the earlier events give
              the backtester more than one sample to score.
* chop     -- a flat base price and flat volume for the whole session. Nothing
              ever fires, which exercises the silent-discard path.

Closes are held exactly flat between events on purpose. Equal closes make the
fast and slow EMAs identical, so the cross rule cannot trip spuriously and the
"no confirmation" case stays deterministic.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from app.domain import Bar, Direction

# 9:30 ET == 13:30 UTC during US market hours.
_SESSION_OPEN_HOUR = 13
_SESSION_OPEN_MINUTE = 30

OPENING_RANGE_BARS = 15
_EVENT_PERIOD = 37          # bars between event bars
_FIRST_EVENT = 36           # first event index; safely past the opening range
_EVENT_MOVE_PCT = 0.012     # ~1.2% -- clears a 0.1% ORB threshold comfortably
_BASE_VOLUME = 10_000.0
_EVENT_VOLUME_MULTIPLE = 6.0
_WICK = 0.02                # constant high/low padding around the body


def seed_of(ticker: str) -> int:
    return int(hashlib.sha256(ticker.upper().encode()).hexdigest()[:8], 16)


def breaks_out(ticker: str) -> bool:
    """Whether this ticker's series contains confirmable event bars."""
    return seed_of(ticker) % 2 == 0


def mock_direction(ticker: str) -> Direction:
    return Direction.BULLISH if seed_of(ticker) % 4 != 3 else Direction.BEARISH


def _session_start(reference: datetime) -> datetime:
    return reference.astimezone(timezone.utc).replace(
        hour=_SESSION_OPEN_HOUR,
        minute=_SESSION_OPEN_MINUTE,
        second=0,
        microsecond=0,
    )


def is_event_bar(index: int, count: int, *, will_break: bool) -> bool:
    """True when bar `index` should be a decisive move."""
    if not will_break:
        return False
    if index == count - 1:
        return True  # the newest bar always gives live confirmation something
    return index >= _FIRST_EVENT and (index - _FIRST_EVENT) % _EVENT_PERIOD == 0


def generate_bars(ticker: str, limit: int, *, as_of: datetime | None = None) -> list[Bar]:
    """Build a deterministic 1-minute series for `ticker`.

    Args:
        ticker: Drives the base price, direction, and which shape is produced.
        limit: Number of bars requested (a floor of 40 is applied so indicators
            with a 21-period lookback always have enough history).
        as_of: Session date to anchor to. Defaults to today.
    """
    count = max(limit, 40)
    start = _session_start(as_of or datetime.now(timezone.utc))
    seed = seed_of(ticker)
    base = 50.0 + (seed % 200)
    direction = mock_direction(ticker)
    will_break = breaks_out(ticker)
    sign = 1.0 if direction is Direction.BULLISH else -1.0

    bars: list[Bar] = []
    for i in range(count):
        ts = start + timedelta(minutes=i)
        event = is_event_bar(i, count, will_break=will_break)

        if event:
            close = base * (1.0 + sign * _EVENT_MOVE_PCT)
            volume = _BASE_VOLUME * _EVENT_VOLUME_MULTIPLE + (seed % 500)
        else:
            close = base
            # Small, bounded volume variation: never enough to look like a spike.
            volume = _BASE_VOLUME + ((seed >> (i % 12)) % 400)

        # The bar opens where the previous one closed.
        open_ = bars[-1].close if bars else base
        high = max(open_, close) + _WICK
        low = min(open_, close) - _WICK

        bars.append(
            Bar(
                ts=ts,
                open=round(open_, 4),
                high=round(high, 4),
                low=round(low, 4),
                close=round(close, 4),
                volume=float(volume),
            )
        )
    return bars
