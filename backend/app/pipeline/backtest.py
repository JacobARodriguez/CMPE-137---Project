"""Backtesting over historical bars.

The whole point of this module is that it contains no rule logic. It sweeps an
index across a historical series and calls `evaluate_rule_set` -- the exact
function the live confirmation engine calls -- so a rule cannot behave one way
here and another way live.

No look-ahead
-------------
At each step the evaluator is given `index=i`, which restricts it to `bars[:i+1]`.
The forward return used to score the signal is measured from bar `i` to bar
`i + horizon`, and a signal within `horizon` bars of the end is skipped rather
than scored against data that does not exist yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.domain import Bar, Direction, RuleSet
from app.pipeline.rules import evaluate_rule_set


@dataclass(frozen=True, slots=True)
class BacktestSignal:
    """One historical firing of the rule set."""

    index: int
    bar_ts: str
    entry_price: float
    exit_price: float
    move_pct: float
    favorable: bool
    rule_tags: list[str]


@dataclass(slots=True)
class BacktestResult:
    ticker: str
    direction: Direction
    horizon_bars: int
    bars_tested: int
    signals: list[BacktestSignal] = field(default_factory=list)

    @property
    def signal_count(self) -> int:
        return len(self.signals)

    @property
    def hit_rate(self) -> float:
        """Share of signals that moved the predicted way."""
        if not self.signals:
            return 0.0
        wins = sum(1 for s in self.signals if s.favorable)
        return round(wins / len(self.signals), 4)

    @property
    def average_move_pct(self) -> float:
        """Mean signed move in the predicted direction."""
        if not self.signals:
            return 0.0
        return round(sum(s.move_pct for s in self.signals) / len(self.signals), 4)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "direction": self.direction.value,
            "horizon_bars": self.horizon_bars,
            "bars_tested": self.bars_tested,
            "signal_count": self.signal_count,
            "hit_rate": self.hit_rate,
            "average_move_pct": self.average_move_pct,
            "signals": [
                {
                    "index": s.index,
                    "bar_ts": s.bar_ts,
                    "entry_price": round(s.entry_price, 2),
                    "exit_price": round(s.exit_price, 2),
                    "move_pct": round(s.move_pct, 2),
                    "favorable": s.favorable,
                    "rule_tags": s.rule_tags,
                }
                for s in self.signals
            ],
        }


def run_backtest(
    ticker: str,
    bars: Sequence[Bar],
    rule_set: RuleSet,
    direction: Direction,
    *,
    horizon_bars: int = 15,
    warmup_bars: int = 25,
) -> BacktestResult:
    """Replay `rule_set` across `bars` and score each firing.

    Args:
        ticker: Label for the result.
        bars: Ascending-by-time history.
        rule_set: The rules to replay.
        direction: Catalyst direction to evaluate against, exactly as live.
        horizon_bars: How many bars forward to measure the move over.
        warmup_bars: Skip this many leading bars so indicators have history.

    Returns:
        BacktestResult with per-signal detail plus hit-rate and average move.
    """
    result = BacktestResult(
        ticker=ticker,
        direction=direction,
        horizon_bars=horizon_bars,
        bars_tested=0,
    )
    if not bars:
        return result

    # Stop `horizon_bars` short: a signal we cannot score yet must not be
    # counted, and must certainly not peek past the end of the series.
    last_scorable = len(bars) - horizon_bars - 1
    for i in range(warmup_bars, max(warmup_bars, last_scorable + 1)):
        result.bars_tested += 1
        confirmation = evaluate_rule_set(bars, rule_set, direction, index=i)
        if not confirmation.confirmed:
            continue

        entry = bars[i].close
        exit_ = bars[i + horizon_bars].close
        if entry <= 0:
            continue

        raw_move = (exit_ - entry) / entry * 100.0
        # Express the move in the direction the signal predicted, so a
        # profitable short reads as positive.
        signed = raw_move if direction is Direction.BULLISH else -raw_move

        result.signals.append(
            BacktestSignal(
                index=i,
                bar_ts=bars[i].ts.isoformat(),
                entry_price=entry,
                exit_price=exit_,
                move_pct=signed,
                favorable=signed > 0,
                rule_tags=confirmation.rule_tags,
            )
        )
    return result
