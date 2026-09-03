"""Technical rule evaluation.

`evaluate_rule_set` is the single entry point used by BOTH the live
confirmation engine and the backtester -- the only difference between them is
which bars get handed in. That is deliberate: a rule can never behave one way
in a backtest and another way live, because there is only one implementation.

No-look-ahead contract
----------------------
Callers pass `index` to mean "evaluate as if the last bar we know about is
bars[index]". Everything downstream sees `bars[: index + 1]` and nothing more,
so a backtest sweeping index 0..N-1 reproduces exactly what the live engine
would have seen at each of those moments.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain import (
    Bar,
    Combinator,
    ConfirmationResult,
    Direction,
    RuleHit,
    RuleSet,
    RuleSpec,
    RuleType,
)
from app.pipeline.indicators import average_volume, ema, opening_range, vwap

# Defaults applied when a rule's params omit a field.
RULE_DEFAULTS: dict[RuleType, dict] = {
    RuleType.ORB: {"minutes": 15, "threshold_pct": 0.1},
    RuleType.EMA_CROSS: {"fast": 9, "slow": 21},
    RuleType.VOLUME_SPIKE: {"lookback": 20, "multiple": 2.0},
    RuleType.VWAP_RECLAIM: {"lookback": 30},
}


def _param(spec: RuleSpec, key: str):
    return spec.params.get(key, RULE_DEFAULTS[spec.type][key])


def _eval_orb(bars: Sequence[Bar], spec: RuleSpec, direction: Direction) -> RuleHit | None:
    """Opening-range breakout: price closes beyond the opening range."""
    minutes = int(_param(spec, "minutes"))
    threshold_pct = float(_param(spec, "threshold_pct"))
    rng = opening_range(bars, minutes)
    if rng is None:
        return None
    high, low = rng
    close = bars[-1].close
    if direction is Direction.BULLISH:
        trigger = high * (1.0 + threshold_pct / 100.0)
        if close > trigger:
            return RuleHit(
                RuleType.ORB,
                direction,
                f"Broke above the {minutes}m opening range high of {high:.2f} "
                f"(close {close:.2f})",
            )
    else:
        trigger = low * (1.0 - threshold_pct / 100.0)
        if close < trigger:
            return RuleHit(
                RuleType.ORB,
                direction,
                f"Broke below the {minutes}m opening range low of {low:.2f} "
                f"(close {close:.2f})",
            )
    return None


def _eval_ema_cross(bars: Sequence[Bar], spec: RuleSpec, direction: Direction) -> RuleHit | None:
    """Fast EMA on the correct side of slow EMA, having crossed on this bar."""
    fast_p = int(_param(spec, "fast"))
    slow_p = int(_param(spec, "slow"))
    closes = [b.close for b in bars]
    if len(closes) < slow_p + 1:
        return None

    fast_now, slow_now = ema(closes, fast_p), ema(closes, slow_p)
    fast_prev, slow_prev = ema(closes[:-1], fast_p), ema(closes[:-1], slow_p)
    if None in (fast_now, slow_now, fast_prev, slow_prev):
        return None

    crossed_up = fast_prev <= slow_prev and fast_now > slow_now
    crossed_down = fast_prev >= slow_prev and fast_now < slow_now
    if direction is Direction.BULLISH and crossed_up:
        return RuleHit(
            RuleType.EMA_CROSS,
            direction,
            f"EMA {fast_p} crossed above EMA {slow_p} "
            f"({fast_now:.2f} vs {slow_now:.2f})",
        )
    if direction is Direction.BEARISH and crossed_down:
        return RuleHit(
            RuleType.EMA_CROSS,
            direction,
            f"EMA {fast_p} crossed below EMA {slow_p} "
            f"({fast_now:.2f} vs {slow_now:.2f})",
        )
    return None


def _eval_volume_spike(bars: Sequence[Bar], spec: RuleSpec, direction: Direction) -> RuleHit | None:
    """Current bar's volume is a multiple of recent average, moving the right way."""
    lookback = int(_param(spec, "lookback"))
    multiple = float(_param(spec, "multiple"))
    avg = average_volume(bars, lookback)
    if avg is None or avg <= 0:
        return None
    last = bars[-1]
    ratio = last.volume / avg
    if ratio < multiple:
        return None
    # A volume spike only confirms if the bar itself agrees with the direction.
    bar_is_up = last.close >= last.open
    if (direction is Direction.BULLISH) != bar_is_up:
        return None
    return RuleHit(
        RuleType.VOLUME_SPIKE,
        direction,
        f"Volume {ratio:.1f}x the {lookback}-bar average",
    )


def _eval_vwap_reclaim(bars: Sequence[Bar], spec: RuleSpec, direction: Direction) -> RuleHit | None:
    """Price crosses back through VWAP in the direction of the catalyst."""
    lookback = int(_param(spec, "lookback"))
    if len(bars) < 2:
        return None
    window = bars[-lookback:] if lookback > 0 else bars
    level = vwap(window)
    prev_level = vwap(window[:-1])
    if level is None or prev_level is None:
        return None
    prev_close, close = bars[-2].close, bars[-1].close
    if direction is Direction.BULLISH and prev_close <= prev_level and close > level:
        return RuleHit(
            RuleType.VWAP_RECLAIM, direction, f"Reclaimed VWAP at {level:.2f}"
        )
    if direction is Direction.BEARISH and prev_close >= prev_level and close < level:
        return RuleHit(
            RuleType.VWAP_RECLAIM, direction, f"Lost VWAP at {level:.2f}"
        )
    return None


_EVALUATORS = {
    RuleType.ORB: _eval_orb,
    RuleType.EMA_CROSS: _eval_ema_cross,
    RuleType.VOLUME_SPIKE: _eval_volume_spike,
    RuleType.VWAP_RECLAIM: _eval_vwap_reclaim,
}


def evaluate_rule_set(
    bars: Sequence[Bar],
    rule_set: RuleSet,
    direction: Direction,
    index: int | None = None,
) -> ConfirmationResult:
    """Evaluate `rule_set` against the bars visible at `index`.

    Args:
        bars: Ascending-by-time bar series.
        rule_set: The user's configured rules and AND/OR combinator.
        direction: The catalyst's direction. A rule only counts as a hit when it
            fires in this direction, so a bullish catalyst is never confirmed by
            a bearish breakout.
        index: Treat `bars[index]` as the latest known bar. Defaults to the last
            bar. Bars after `index` are never read -- this is the no-look-ahead
            guarantee the backtester depends on.

    Returns:
        ConfirmationResult with every rule that fired and whether the set as a
        whole is satisfied.
    """
    if not bars:
        return ConfirmationResult(False, (), _now_of(bars, index))

    end = len(bars) - 1 if index is None else index
    if end < 0 or end >= len(bars):
        raise IndexError(f"index {index} out of range for {len(bars)} bars")
    visible = bars[: end + 1]

    active = [r for r in rule_set.rules if r.enabled]
    if not active:
        return ConfirmationResult(False, (), visible[-1].ts)

    hits: list[RuleHit] = []
    for spec in active:
        evaluator = _EVALUATORS.get(spec.type)
        if evaluator is None:
            continue
        hit = evaluator(visible, spec, direction)
        if hit is not None:
            hits.append(hit)

    if rule_set.combinator is Combinator.AND:
        confirmed = len(hits) == len(active)
    else:
        confirmed = len(hits) > 0

    return ConfirmationResult(confirmed, tuple(hits), visible[-1].ts)


def _now_of(bars: Sequence[Bar], index: int | None):
    from app.domain import utcnow

    if not bars:
        return utcnow()
    end = len(bars) - 1 if index is None else index
    return bars[max(0, min(end, len(bars) - 1))].ts
