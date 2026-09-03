"""Materiality scoring for TEXT catalysts.

Only unstructured text (8-K bodies, press releases, transcript excerpts) reaches
this layer. Numeric catalysts -- EPS surprise %, insider dollar value, options
premium -- carry their own magnitude and skip scoring entirely; see
`app.pipeline.catalysts`.

Three interchangeable backends, selected by MATERIALITY_BACKEND:

* mock    -- keyword heuristic in `app.services.mocks`. The default. No network,
             no model download, fully deterministic.
* claude  -- one structured Claude call per document.
* finbert -- local FinBERT sentiment via transformers. No network at inference
             time once the model is cached, but a heavy dependency.

Both real backends fall back to the heuristic on any failure. A scorer outage
should degrade catalyst quality, never take down the pipeline.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.domain import Direction
from app.services.base import MaterialityScore
from app.services.mocks import MockMaterialityScorer

logger = logging.getLogger(__name__)

# Keep well clear of the 1M context window; filings can be long and we only
# need the disclosure's substance, not its exhibits.
MAX_TEXT_CHARS = 24_000

_SYSTEM_PROMPT = """\
You are a materiality classifier for short-term equity trading.

Given a company disclosure, judge how likely it is to move the stock within the
next trading session, and in which direction.

Score guidance:
  0.0-0.2  routine or administrative (minor 8-K items, boilerplate)
  0.2-0.5  notable but unlikely to move price much on its own
  0.5-0.8  clearly market-relevant (guidance change, major contract, litigation)
  0.8-1.0  decisive (M&A, bankruptcy, restatement, large guidance revision)

Judge only the disclosure's own content. Do not speculate beyond it, and do not
give investment advice -- this is a classification task feeding a research tool.\
"""


class _MaterialityOutput(BaseModel):
    """Schema the model is constrained to return."""

    score: float = Field(ge=0.0, le=1.0, description="0-1 materiality")
    direction: str = Field(description='Either "bullish" or "bearish"')
    rationale: str = Field(description="One sentence, under 200 characters")


def _coerce(out: _MaterialityOutput) -> MaterialityScore:
    direction = (
        Direction.BEARISH if out.direction.strip().lower() == "bearish" else Direction.BULLISH
    )
    return MaterialityScore(
        score=round(max(0.0, min(1.0, out.score)), 4),
        direction=direction,
        rationale=out.rationale.strip()[:200],
    )


class ClaudeMaterialityScorer:
    """Structured single-call scoring via the Anthropic API."""

    MODEL = "claude-opus-5"

    def __init__(self, api_key: str | None = None) -> None:
        import anthropic  # imported lazily so the dependency stays optional

        self._client = (
            anthropic.AsyncAnthropic(api_key=api_key)
            if api_key
            else anthropic.AsyncAnthropic()
        )
        self._fallback = MockMaterialityScorer()

    async def score(self, ticker: str, text: str) -> MaterialityScore:
        excerpt = text[:MAX_TEXT_CHARS]
        try:
            response = await self._client.messages.parse(
                model=self.MODEL,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                # Classification is a shallow task; low effort keeps it cheap
                # and fast without hurting accuracy here.
                output_config={"effort": "low"},
                messages=[
                    {
                        "role": "user",
                        "content": f"Ticker: {ticker}\n\nDisclosure:\n{excerpt}",
                    }
                ],
                output_format=_MaterialityOutput,
            )
            # A policy decline returns HTTP 200 with no usable content, so check
            # before touching the parsed output.
            if response.stop_reason == "refusal":
                logger.warning(
                    "Claude declined to score %s; using heuristic fallback", ticker
                )
                return await self._fallback.score(ticker, text)

            parsed = response.parsed_output
            if parsed is None:
                logger.warning("Empty parse for %s; using heuristic fallback", ticker)
                return await self._fallback.score(ticker, text)
            return _coerce(parsed)

        except Exception:  # noqa: BLE001 - degrade, never take down the pipeline
            logger.exception("Claude materiality scoring failed for %s", ticker)
            return await self._fallback.score(ticker, text)


class FinBertMaterialityScorer:
    """Local FinBERT sentiment, mapped onto the materiality interface.

    FinBERT emits positive/negative/neutral sentiment rather than materiality as
    such. We treat confidence in a non-neutral label as the materiality proxy,
    which is a reasonable approximation and keeps the interface uniform.
    """

    MODEL_NAME = "ProsusAI/finbert"

    def __init__(self) -> None:
        from transformers import pipeline  # lazy: heavy optional dependency

        self._pipe = pipeline("sentiment-analysis", model=self.MODEL_NAME)
        self._fallback = MockMaterialityScorer()

    async def score(self, ticker: str, text: str) -> MaterialityScore:
        try:
            # FinBERT is a 512-token model; feed it the lede, which is where a
            # disclosure states its substance.
            result = self._pipe(text[:1500], truncation=True)[0]
            label = str(result["label"]).lower()
            confidence = float(result["score"])

            if label == "neutral":
                return MaterialityScore(
                    score=round(max(0.0, 1.0 - confidence), 4),
                    direction=Direction.BULLISH,
                    rationale=f"FinBERT neutral ({confidence:.2f})",
                )
            direction = Direction.BULLISH if label == "positive" else Direction.BEARISH
            return MaterialityScore(
                score=round(confidence, 4),
                direction=direction,
                rationale=f"FinBERT {label} ({confidence:.2f})",
            )
        except Exception:  # noqa: BLE001
            logger.exception("FinBERT scoring failed for %s", ticker)
            return await self._fallback.score(ticker, text)
