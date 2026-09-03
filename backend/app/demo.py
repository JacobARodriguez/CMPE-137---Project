"""Offline pipeline demo.

    python -m app.demo

Runs the full catalyst -> confirmation -> rank pipeline against mock data with
no keys, no database, and no Redis, then prints what each stage produced. Handy
for seeing the fan-out guarantee hold and for checking a rule change end to end
without starting the server.
"""

from __future__ import annotations

import asyncio

from app.config import Settings
from app.domain import Combinator, RuleSet, RuleSpec, RuleType
from app.pipeline.backtest import run_backtest
from app.pipeline.ranking import build_ranker
from app.pipeline.runner import PipelineRunner, group_watchers
from app.pipeline.windows import InMemoryWindowStore
from app.services._series import breaks_out, generate_bars, mock_direction
from app.services.registry import build_services

WATCHED = ["AAPL", "TSLA", "NVDA", "AMD", "MSFT", "SOFI"]

DEFAULT_RULES = RuleSet(
    id=1,
    name="Default (any rule)",
    combinator=Combinator.OR,
    rules=(
        RuleSpec(RuleType.ORB),
        RuleSpec(RuleType.EMA_CROSS),
        RuleSpec(RuleType.VOLUME_SPIKE),
        RuleSpec(RuleType.VWAP_RECLAIM),
    ),
)
TIGHT_RULES = RuleSet(
    id=2,
    name="Tight (breakout + volume)",
    combinator=Combinator.AND,
    rules=(RuleSpec(RuleType.ORB), RuleSpec(RuleType.VOLUME_SPIKE)),
)


def _rule(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


async def main() -> None:
    settings = Settings(_env_file=None)
    services = build_services(settings)

    _rule("Providers")
    for name, impl in services.selection.items():
        print(f"  {name:<14} {impl}")

    _rule("Mock series shape")
    for ticker in WATCHED:
        shape = "breakout" if breaks_out(ticker) else "chop"
        print(f"  {ticker:<6} {shape:<9} {mock_direction(ticker).value}")

    # Users 1 and 2 share a rule set; user 3 has a stricter one.
    rows = []
    for ticker in WATCHED:
        rows.append((ticker, 1, DEFAULT_RULES))
        rows.append((ticker, 2, DEFAULT_RULES))
        rows.append((ticker, 3, TIGHT_RULES))

    runner = PipelineRunner(services, InMemoryWindowStore(), build_ranker())
    alerts, report = await runner.run_cycle(group_watchers(rows))

    _rule("Cycle report")
    print(f"  watchers            {len(rows)} (3 users x {len(WATCHED)} tickers)")
    print(f"  tickers polled      {report.tickers_polled}")
    print(f"  external fetches    {report.external_fetches}")
    print(f"  DUPLICATE fetches   {report.duplicate_fetches}   <- must be 0")
    print(f"  catalysts detected  {report.catalysts_detected}")
    print(f"  rule evaluations    {report.rule_evaluations} "
          f"(2 distinct rule sets, not {len(rows)})")
    print(f"  alerts confirmed    {report.alerts_confirmed}")
    if report.errors:
        print(f"  errors              {report.errors}")

    _rule("Top alerts")
    for alert in alerts[:5]:
        tags = ",".join(alert.confirmation.rule_tags)
        print(f"  {alert.ticker:<6} user{alert.user_id}  "
              f"{alert.direction.value:<8} {alert.confidence:.2f}  [{tags}]")
        print(f"         {alert.why[:96]}")

    _rule("Backtest (same rule function as live confirmation)")
    for ticker in ["AAPL", "AMD"]:
        bars = generate_bars(ticker, 300)
        result = run_backtest(ticker, bars, DEFAULT_RULES, mock_direction(ticker))
        print(f"  {ticker:<6} bars={result.bars_tested:<4} "
              f"signals={result.signal_count:<3} "
              f"hit_rate={result.hit_rate:<6} avg_move={result.average_move_pct}%")
    print(
        "\n  Note: mock bars snap back to base after each event, so a negative\n"
        "  average move here is the backtester measuring honestly, not a bug."
    )


if __name__ == "__main__":
    asyncio.run(main())
