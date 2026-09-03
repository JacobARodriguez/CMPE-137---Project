"""Pure indicator maths over a bar series.

Every function takes the bars it is allowed to see and nothing more. Callers
slice the series; these helpers never look past the end of what they are given,
which is what keeps the backtest honest.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain import Bar


def ema(values: Sequence[float], period: int) -> float | None:
    """Exponential moving average of the final `period`-anchored window.

    Seeded with a simple moving average of the first `period` values, then
    smoothed forward. Returns None when there is not enough history.
    """
    if period <= 0 or len(values) < period:
        return None
    k = 2.0 / (period + 1.0)
    seed = sum(values[:period]) / period
    result = seed
    for v in values[period:]:
        result = v * k + result * (1.0 - k)
    return result


def vwap(bars: Sequence[Bar]) -> float | None:
    """Volume-weighted average price over the supplied bars."""
    total_volume = sum(b.volume for b in bars)
    if total_volume <= 0:
        return None
    typical = sum(((b.high + b.low + b.close) / 3.0) * b.volume for b in bars)
    return typical / total_volume


def average_volume(bars: Sequence[Bar], lookback: int) -> float | None:
    """Mean volume of the `lookback` bars ending just before the last bar."""
    if lookback <= 0 or len(bars) < lookback + 1:
        return None
    window = bars[-(lookback + 1) : -1]
    return sum(b.volume for b in window) / len(window)


def opening_range(bars: Sequence[Bar], minutes: int) -> tuple[float, float] | None:
    """(high, low) of the first `minutes` of the most recent session.

    Bars are assumed to be 1-minute. The session is identified by the calendar
    date of the last bar, so a series spanning several days still measures the
    opening range of the day being evaluated.
    """
    if not bars or minutes <= 0:
        return None
    session_date = bars[-1].ts.date()
    session = [b for b in bars if b.ts.date() == session_date]
    if not session:
        return None
    window = session[:minutes]
    if len(window) < min(minutes, len(session)):
        return None
    return max(b.high for b in window), min(b.low for b in window)
