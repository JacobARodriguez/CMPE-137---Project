"""Offline tests for the pipeline. No network, no database, no keys."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.config import Settings
from app.domain import (
    Bar,
    Catalyst,
    CatalystSource,
    CatalystType,
    Combinator,
    Direction,
    RuleSet,
    RuleSpec,
    RuleType,
    utcnow,
)
from app.pipeline.backtest import run_backtest
from app.pipeline.ranking import HeuristicRanker, RankingInput, build_ranker
from app.pipeline.rules import evaluate_rule_set
from app.pipeline.runner import PipelineRunner, group_watchers
from app.pipeline.windows import InMemoryWindowStore
from app.services._series import breaks_out, generate_bars, mock_direction
from app.services.registry import build_services

pytestmark = pytest.mark.asyncio

DEFAULT_RULES = RuleSet(
    id=1,
    name="Default",
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
    name="Tight",
    combinator=Combinator.AND,
    rules=(RuleSpec(RuleType.ORB), RuleSpec(RuleType.VOLUME_SPIKE)),
)

BREAKOUT_TICKER = "AAPL"   # breaks_out() is True
CHOP_TICKER = "AMD"        # breaks_out() is False


def _offline_settings() -> Settings:
    # _env_file=None so a developer's real .env cannot leak into the tests.
    return Settings(_env_file=None)


# --------------------------------------------------------------- rules -------


class TestRuleEvaluation:
    async def test_breakout_confirms(self):
        bars = generate_bars(BREAKOUT_TICKER, 120)
        result = evaluate_rule_set(
            bars, DEFAULT_RULES, mock_direction(BREAKOUT_TICKER)
        )
        assert result.confirmed
        assert "orb" in result.rule_tags
        assert "volume_spike" in result.rule_tags

    async def test_chop_never_confirms(self):
        assert not breaks_out(CHOP_TICKER)
        bars = generate_bars(CHOP_TICKER, 120)
        result = evaluate_rule_set(bars, DEFAULT_RULES, mock_direction(CHOP_TICKER))
        assert not result.confirmed
        assert result.rule_tags == []

    async def test_direction_must_match(self):
        """A bullish setup must not confirm a bearish catalyst."""
        bars = generate_bars(BREAKOUT_TICKER, 120)
        wrong = mock_direction(BREAKOUT_TICKER).opposite
        assert not evaluate_rule_set(bars, DEFAULT_RULES, wrong).confirmed

    async def test_and_combinator_is_stricter_than_or(self):
        bars = generate_bars(BREAKOUT_TICKER, 120)
        direction = mock_direction(BREAKOUT_TICKER)
        or_hits = len(evaluate_rule_set(bars, DEFAULT_RULES, direction).hits)
        and_result = evaluate_rule_set(bars, TIGHT_RULES, direction)
        assert and_result.confirmed
        assert len(and_result.hits) <= or_hits

    async def test_and_requires_every_rule(self):
        """AND with a rule that cannot fire must not confirm."""
        rule_set = RuleSet(
            name="Impossible",
            combinator=Combinator.AND,
            rules=(
                RuleSpec(RuleType.ORB),
                # A 500x volume multiple never happens in the mock series.
                RuleSpec(RuleType.VOLUME_SPIKE, {"lookback": 20, "multiple": 500.0}),
            ),
        )
        bars = generate_bars(BREAKOUT_TICKER, 120)
        result = evaluate_rule_set(bars, rule_set, mock_direction(BREAKOUT_TICKER))
        assert not result.confirmed

    async def test_empty_bars_do_not_crash(self):
        assert not evaluate_rule_set([], DEFAULT_RULES, Direction.BULLISH).confirmed

    async def test_disabled_rules_are_ignored(self):
        rule_set = RuleSet(
            name="AllOff",
            combinator=Combinator.OR,
            rules=(RuleSpec(RuleType.ORB, enabled=False),),
        )
        bars = generate_bars(BREAKOUT_TICKER, 120)
        assert not evaluate_rule_set(
            bars, rule_set, mock_direction(BREAKOUT_TICKER)
        ).confirmed


class TestNoLookAhead:
    """The backtest's correctness rests entirely on these."""

    async def test_index_restricts_visible_bars(self):
        bars = generate_bars(BREAKOUT_TICKER, 120)
        direction = mock_direction(BREAKOUT_TICKER)
        # Bar 20 is before the first event bar (36), so nothing can have fired.
        assert not evaluate_rule_set(bars, DEFAULT_RULES, direction, index=20).confirmed
        assert evaluate_rule_set(bars, DEFAULT_RULES, direction, index=36).confirmed

    async def test_future_bars_cannot_change_the_past(self):
        """Appending future bars must not alter a past evaluation."""
        short = generate_bars(BREAKOUT_TICKER, 60)
        long = generate_bars(BREAKOUT_TICKER, 200)
        direction = mock_direction(BREAKOUT_TICKER)
        for i in (30, 40, 50):
            assert (
                evaluate_rule_set(short, DEFAULT_RULES, direction, index=i).confirmed
                == evaluate_rule_set(long, DEFAULT_RULES, direction, index=i).confirmed
            )

    async def test_index_out_of_range_raises(self):
        bars = generate_bars(BREAKOUT_TICKER, 60)
        with pytest.raises(IndexError):
            evaluate_rule_set(bars, DEFAULT_RULES, Direction.BULLISH, index=999)


# ------------------------------------------------------------ fan-out --------


class TestFanOut:
    """The core architectural rule: one poll per ticker, never per user."""

    async def test_one_fetch_per_ticker_regardless_of_user_count(self):
        services = build_services(_offline_settings())
        runner = PipelineRunner(services, InMemoryWindowStore(), build_ranker())

        tickers = ["AAPL", "TSLA", "AMD"]
        rows = [(t, uid, DEFAULT_RULES) for t in tickers for uid in range(1, 26)]
        _, report = await runner.run_cycle(group_watchers(rows))

        assert report.tickers_polled == len(tickers)
        assert report.external_fetches == len(tickers)
        assert report.duplicate_fetches == 0

    async def test_identical_rule_sets_are_evaluated_once(self):
        """25 users sharing one rule set must cause one evaluation per catalyst."""
        services = build_services(_offline_settings())
        runner = PipelineRunner(services, InMemoryWindowStore(), build_ranker())

        shared = [("AAPL", uid, DEFAULT_RULES) for uid in range(1, 26)]
        _, shared_report = await runner.run_cycle(group_watchers(shared))

        services2 = build_services(_offline_settings())
        runner2 = PipelineRunner(services2, InMemoryWindowStore(), build_ranker())
        one = [("AAPL", 1, DEFAULT_RULES)]
        _, one_report = await runner2.run_cycle(group_watchers(one))

        assert shared_report.rule_evaluations == one_report.rule_evaluations

    async def test_distinct_rule_sets_each_evaluate(self):
        services = build_services(_offline_settings())
        runner = PipelineRunner(services, InMemoryWindowStore(), build_ranker())
        rows = [("AAPL", 1, DEFAULT_RULES), ("AAPL", 2, TIGHT_RULES)]
        _, report = await runner.run_cycle(group_watchers(rows))
        # Two distinct fingerprints, so two evaluations per open catalyst.
        assert report.rule_evaluations == 2 * report.catalysts_detected

    async def test_every_watching_user_gets_the_alert(self):
        services = build_services(_offline_settings())
        runner = PipelineRunner(services, InMemoryWindowStore(), build_ranker())
        rows = [("AAPL", uid, DEFAULT_RULES) for uid in (1, 2, 3)]
        alerts, _ = await runner.run_cycle(group_watchers(rows))
        assert {a.user_id for a in alerts} == {1, 2, 3}

    async def test_empty_watchlist_is_a_no_op(self):
        services = build_services(_offline_settings())
        runner = PipelineRunner(services, InMemoryWindowStore(), build_ranker())
        alerts, report = await runner.run_cycle({})
        assert alerts == []
        assert report.tickers_polled == 0

    async def test_alerts_are_sorted_by_confidence(self):
        services = build_services(_offline_settings())
        runner = PipelineRunner(services, InMemoryWindowStore(), build_ranker())
        rows = [(t, 1, DEFAULT_RULES) for t in ["AAPL", "TSLA", "NVDA", "SOFI"]]
        alerts, _ = await runner.run_cycle(group_watchers(rows))
        confidences = [a.confidence for a in alerts]
        assert confidences == sorted(confidences, reverse=True)


# ------------------------------------------------------------- windows -------


class TestWindows:
    async def test_expired_catalysts_are_purged(self):
        store = InMemoryWindowStore()
        stale = Catalyst(
            ticker="AAPL",
            type=CatalystType.NEWS,
            source=CatalystSource.ALPACA,
            direction=Direction.BULLISH,
            magnitude=0.5,
            detected_at=utcnow() - timedelta(hours=5),
            window_expires_at=utcnow() - timedelta(hours=4),
            headline="stale",
        )
        await store.open_window(stale)
        assert await store.active("AAPL") == []
        assert await store.purge_expired() == 1

    async def test_active_returns_open_windows(self):
        store = InMemoryWindowStore()
        fresh = Catalyst(
            ticker="AAPL",
            type=CatalystType.NEWS,
            source=CatalystSource.ALPACA,
            direction=Direction.BULLISH,
            magnitude=0.5,
            detected_at=utcnow(),
            window_expires_at=utcnow() + timedelta(hours=1),
            headline="fresh",
        )
        await store.open_window(fresh)
        assert len(await store.active("AAPL")) == 1


# ------------------------------------------------------------- ranking -------


class TestRanking:
    def _input(self, catalyst_type: CatalystType, magnitude: float, hits: int):
        bars = generate_bars(BREAKOUT_TICKER, 120)
        confirmation = evaluate_rule_set(
            bars, DEFAULT_RULES, mock_direction(BREAKOUT_TICKER)
        )
        catalyst = Catalyst(
            ticker="AAPL",
            type=catalyst_type,
            source=CatalystSource.FINNHUB,
            direction=Direction.BULLISH,
            magnitude=magnitude,
            detected_at=utcnow(),
            window_expires_at=utcnow() + timedelta(hours=1),
            headline="test",
        )
        return RankingInput(catalyst=catalyst, confirmation=confirmation)

    async def test_score_is_bounded(self):
        ranker = HeuristicRanker()
        score = ranker.score(self._input(CatalystType.EARNINGS_SURPRISE, 1.0, 4))
        assert 0.0 <= score <= 1.0

    async def test_stronger_magnitude_scores_higher(self):
        ranker = HeuristicRanker()
        weak = ranker.score(self._input(CatalystType.EARNINGS_SURPRISE, 0.1, 4))
        strong = ranker.score(self._input(CatalystType.EARNINGS_SURPRISE, 1.0, 4))
        assert strong > weak

    async def test_explanation_mentions_the_catalyst(self):
        ranker = HeuristicRanker()
        why = ranker.explain(self._input(CatalystType.EARNINGS_SURPRISE, 0.8, 4))
        assert "Confirmed" in why


# ------------------------------------------------------------ backtest -------


class TestBacktest:
    async def test_uses_the_same_rules_as_live(self):
        """A backtest signal index must confirm under the live evaluator too."""
        bars = generate_bars(BREAKOUT_TICKER, 200)
        direction = mock_direction(BREAKOUT_TICKER)
        result = run_backtest(BREAKOUT_TICKER, bars, DEFAULT_RULES, direction)
        assert result.signal_count > 0
        for signal in result.signals:
            assert evaluate_rule_set(
                bars, DEFAULT_RULES, direction, index=signal.index
            ).confirmed

    async def test_no_signal_scored_without_a_full_horizon(self):
        bars = generate_bars(BREAKOUT_TICKER, 200)
        horizon = 15
        result = run_backtest(
            BREAKOUT_TICKER, bars, DEFAULT_RULES, mock_direction(BREAKOUT_TICKER),
            horizon_bars=horizon,
        )
        for signal in result.signals:
            assert signal.index + horizon < len(bars)

    async def test_chop_produces_no_signals(self):
        bars = generate_bars(CHOP_TICKER, 200)
        result = run_backtest(
            CHOP_TICKER, bars, DEFAULT_RULES, mock_direction(CHOP_TICKER)
        )
        assert result.signal_count == 0
        assert result.hit_rate == 0.0

    async def test_empty_series_is_safe(self):
        result = run_backtest("AAPL", [], DEFAULT_RULES, Direction.BULLISH)
        assert result.signal_count == 0


# ------------------------------------------------------------- offline -------


class TestOfflineOperation:
    async def test_everything_is_mocked_with_no_configuration(self):
        services = build_services(_offline_settings())
        assert set(services.selection.values()) <= {"mock", "paper_mock"}

    async def test_execution_never_reaches_a_broker(self):
        from app.services.base import OrderRequest

        services = build_services(_offline_settings())
        receipt = await services.execution.submit(
            OrderRequest(ticker="AAPL", side="buy", quantity=1)
        )
        assert receipt.accepted
        assert "No broker" in receipt.detail
