"""The pipeline orchestrator.

Architectural rule this module exists to enforce
------------------------------------------------
Poll each watchlisted ticker ONCE per interval, run catalyst detection ONCE, and
fan the results out to every user watching that ticker. No client ever reaches an
external API, and no ticker is fetched twice because two users happen to watch it.

Confirmation needs care, because technical rules are per-user configurable while
the expensive work is not:

    external I/O   -- once per TICKER          (bars, news, flow, filings)
    catalyst detect-- once per TICKER
    rule evaluation-- once per DISTINCT RULE SET among that ticker's watchers
    alert delivery -- per USER

Rule evaluation is pure local computation over already-fetched bars, so running
it per distinct rule set costs nothing external. Identical rule sets are collapsed
by `RuleSet.fingerprint()`, so ten users sharing a default configuration cause one
evaluation, not ten.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain import (
    Alert,
    AlertStatus,
    Bar,
    Catalyst,
    RuleSet,
    utcnow,
)
from app.pipeline.ranking import Ranker, RankingInput
from app.pipeline.rules import evaluate_rule_set
from app.pipeline.windows import WindowStore
from app.services.registry import ServiceBundle

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Watcher:
    """One user's interest in a ticker, with the rules they want applied."""

    user_id: int
    rule_set: RuleSet


@dataclass(slots=True)
class CycleReport:
    """What one poll cycle did. Returned for logging, tests, and /health."""

    started_at: datetime
    tickers_polled: int = 0
    external_fetches: int = 0
    catalysts_detected: int = 0
    rule_evaluations: int = 0
    alerts_confirmed: int = 0
    windows_expired: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def duplicate_fetches(self) -> int:
        """Must always be 0. Non-zero means the fan-out rule was violated."""
        return max(0, self.external_fetches - self.tickers_polled)


class PipelineRunner:
    """Runs catalyst detection and confirmation for a set of watched tickers."""

    def __init__(
        self,
        services: ServiceBundle,
        window_store: WindowStore,
        ranker: Ranker,
        *,
        bar_lookback: int = 200,
        catalyst_lookback: timedelta = timedelta(hours=24),
    ) -> None:
        self._services = services
        self._windows = window_store
        self._ranker = ranker
        self._bar_lookback = bar_lookback
        self._catalyst_lookback = catalyst_lookback

    async def run_cycle(self, watchers_by_ticker: dict[str, list[Watcher]]) -> tuple[list[Alert], CycleReport]:
        """Poll every ticker once and return the alerts confirmed this cycle."""
        report = CycleReport(started_at=utcnow())
        report.windows_expired = await self._windows.purge_expired()

        if not watchers_by_ticker:
            return [], report

        tickers = sorted(watchers_by_ticker)
        report.tickers_polled = len(tickers)

        results = await asyncio.gather(
            *(self._process_ticker(t, watchers_by_ticker[t], report) for t in tickers),
            return_exceptions=True,
        )

        alerts: list[Alert] = []
        for ticker, result in zip(tickers, results):
            if isinstance(result, BaseException):
                # One bad ticker must not sink the cycle.
                logger.exception("Ticker %s failed this cycle", ticker, exc_info=result)
                report.errors.append(f"{ticker}: {result}")
                continue
            alerts.extend(result)

        report.alerts_confirmed = len(alerts)
        # Highest confidence first -- the dashboard's default ordering.
        alerts.sort(key=lambda a: a.confidence, reverse=True)
        return alerts, report

    async def _process_ticker(
        self, ticker: str, watchers: list[Watcher], report: CycleReport
    ) -> list[Alert]:
        # ---- Stage 1: the ONLY external I/O for this ticker this cycle -------
        since = utcnow() - self._catalyst_lookback
        bars, fresh_catalysts = await asyncio.gather(
            self._services.market_data.get_bars(ticker, self._bar_lookback),
            self._detect(ticker, since),
        )
        report.external_fetches += 1
        report.catalysts_detected += len(fresh_catalysts)

        # ---- Stages 2-3 already applied; open a window per catalyst ---------
        for catalyst in fresh_catalysts:
            await self._windows.open_window(catalyst)

        open_catalysts = await self._windows.active(ticker)
        if not open_catalysts or not bars:
            return []

        # ---- Stage 4: confirm, once per DISTINCT rule set -------------------
        distinct: dict[str, RuleSet] = {}
        users_by_fingerprint: dict[str, list[int]] = defaultdict(list)
        for watcher in watchers:
            fp = watcher.rule_set.fingerprint()
            distinct.setdefault(fp, watcher.rule_set)
            users_by_fingerprint[fp].append(watcher.user_id)

        alerts: list[Alert] = []
        for catalyst in open_catalysts:
            confirmed_any = False
            for fingerprint, rule_set in distinct.items():
                result = evaluate_rule_set(bars, rule_set, catalyst.direction)
                report.rule_evaluations += 1
                if not result.confirmed:
                    # Window stays open; it may confirm on a later bar. If it
                    # never does, purge_expired drops it silently.
                    continue

                # ---- Stage 5: rank, then fan out to every matching user -----
                ranking_input = RankingInput(catalyst=catalyst, confirmation=result)
                confidence = self._ranker.score(ranking_input)
                why = self._ranker.explain(ranking_input)

                for user_id in users_by_fingerprint[fingerprint]:
                    alerts.append(
                        Alert(
                            user_id=user_id,
                            ticker=ticker,
                            direction=catalyst.direction,
                            confidence=confidence,
                            why=why,
                            catalyst=catalyst,
                            confirmation=result,
                            rule_set_id=rule_set.id,
                            status=AlertStatus.CONFIRMED,
                        )
                    )

                confirmed_any = True

            # Confirmed once is enough: close the window after every rule set has
            # been given its chance, so the next cycle does not re-fire this
            # catalyst for anyone.
            if confirmed_any and catalyst.id:
                await self._windows.close(ticker, catalyst.id)

        return alerts

    async def _detect(self, ticker: str, since: datetime) -> list[Catalyst]:
        # Imported here to keep the module import graph acyclic.
        from app.pipeline.catalysts import detect_catalysts

        return await detect_catalysts(ticker, self._services, since)


def group_watchers(rows: list[tuple[str, int, RuleSet]]) -> dict[str, list[Watcher]]:
    """Turn (ticker, user_id, rule_set) rows into the runner's input shape."""
    grouped: dict[str, list[Watcher]] = defaultdict(list)
    for ticker, user_id, rule_set in rows:
        grouped[ticker.upper()].append(Watcher(user_id=user_id, rule_set=rule_set))
    return dict(grouped)
