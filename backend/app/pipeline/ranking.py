"""Stage 5: rank confirmed alerts.

The MVP ranker is a transparent weighted heuristic. It sits behind the `Ranker`
protocol so the trained gradient-boosted model planned for phase 2 can replace
it without touching a single caller -- swap the instance in `build_ranker` and
everything downstream is unchanged.

The heuristic is deliberately explainable: `explain()` returns the same
component breakdown that produced the score, which is what the dashboard's
plain-English "why" is built from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.domain import Catalyst, CatalystType, ConfirmationResult, utcnow


@dataclass(frozen=True, slots=True)
class RankingInput:
    catalyst: Catalyst
    confirmation: ConfirmationResult


@runtime_checkable
class Ranker(Protocol):
    def score(self, item: RankingInput) -> float: ...

    def explain(self, item: RankingInput) -> str: ...


# Priors for how tradeable each catalyst class tends to be. These are starting
# values to be replaced by measured hit-rates once the outcomes table has data.
CATALYST_WEIGHTS: dict[CatalystType, float] = {
    CatalystType.EARNINGS_SURPRISE: 1.00,
    CatalystType.OPTIONS_FLOW: 0.90,
    CatalystType.FILING_8K: 0.85,
    CatalystType.INSIDER_BUY: 0.70,
    CatalystType.NEWS: 0.65,
    CatalystType.INSIDER_SELL: 0.55,
}

# Component weights. Must sum to 1.0 so the result is a clean 0..1 confidence.
W_CATALYST_CLASS = 0.30
W_MAGNITUDE = 0.30
W_RULE_AGREEMENT = 0.25
W_FRESHNESS = 0.15


class HeuristicRanker:
    """Weighted blend of catalyst class, strength, rule agreement, freshness."""

    #: Rule hits at or above this count are treated as full agreement.
    FULL_AGREEMENT_HITS = 3

    def _components(self, item: RankingInput) -> dict[str, float]:
        catalyst, confirmation = item.catalyst, item.confirmation

        klass = CATALYST_WEIGHTS.get(catalyst.type, 0.5)
        magnitude = max(0.0, min(catalyst.magnitude, 1.0))
        agreement = min(len(confirmation.hits) / self.FULL_AGREEMENT_HITS, 1.0)

        # Freshness: 1.0 at detection, decaying to 0.0 as the window closes.
        total = (catalyst.window_expires_at - catalyst.detected_at).total_seconds()
        if total <= 0:
            freshness = 0.0
        else:
            elapsed = (utcnow() - catalyst.detected_at).total_seconds()
            freshness = max(0.0, min(1.0 - elapsed / total, 1.0))

        return {
            "catalyst_class": klass,
            "magnitude": magnitude,
            "rule_agreement": agreement,
            "freshness": freshness,
        }

    def score(self, item: RankingInput) -> float:
        c = self._components(item)
        raw = (
            c["catalyst_class"] * W_CATALYST_CLASS
            + c["magnitude"] * W_MAGNITUDE
            + c["rule_agreement"] * W_RULE_AGREEMENT
            + c["freshness"] * W_FRESHNESS
        )
        return round(max(0.0, min(raw, 1.0)), 4)

    def explain(self, item: RankingInput) -> str:
        """Plain-English rationale shown on the alert card."""
        catalyst, confirmation = item.catalyst, item.confirmation
        rules = ", ".join(hit.detail for hit in confirmation.hits) or "no rules fired"
        return (
            f"{catalyst.headline}. "
            f"Confirmed {catalyst.direction.value} by: {rules}."
        )


class ModelRanker:
    """Placeholder for the phase-2 trained ranker.

    Intentionally unimplemented. The outcomes table is the training set; once it
    has enough labelled rows, load the fitted model here and register it in
    `build_ranker`. Nothing else in the codebase needs to change.
    """

    def __init__(self, model_path: str) -> None:
        self._model_path = model_path

    def score(self, item: RankingInput) -> float:
        raise NotImplementedError(
            "The trained ranking model is phase 2. Use HeuristicRanker."
        )

    def explain(self, item: RankingInput) -> str:
        raise NotImplementedError(
            "The trained ranking model is phase 2. Use HeuristicRanker."
        )


def build_ranker() -> Ranker:
    """The single place that picks a ranking implementation."""
    return HeuristicRanker()
