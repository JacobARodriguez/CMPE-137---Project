"""Conversions between database rows and pipeline domain objects, plus the
queries the pipeline needs.

This is the boundary layer. The pipeline never imports SQLAlchemy; the database
never leaks into rule evaluation.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AlertRow, CatalystRow, OutcomeRow, RuleSetRow, WatchlistItem
from app.domain import (
    Alert,
    Catalyst,
    Combinator,
    RuleSet,
    RuleSpec,
    RuleType,
)


def rule_set_to_domain(row: RuleSetRow) -> RuleSet:
    """DB row -> the immutable RuleSet the rule engine consumes."""
    specs: list[RuleSpec] = []
    for r in row.rules:
        try:
            rule_type = RuleType(r.type)
        except ValueError:
            # An unknown rule type is data we cannot evaluate; skip rather than
            # crash the whole cycle for every user sharing this profile.
            continue
        specs.append(RuleSpec(type=rule_type, params=r.params or {}, enabled=r.enabled))

    return RuleSet(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        combinator=Combinator(row.combinator),
        rules=tuple(specs),
    )


async def load_watchers(session: AsyncSession) -> list[tuple[str, int, RuleSet]]:
    """Every (ticker, user, active rule set) triple the pipeline should run.

    One query for watchlist items joined to each user's ACTIVE rule set. Users
    with no active rule set are skipped -- there is nothing to confirm against.
    """
    stmt = (
        select(WatchlistItem.ticker, WatchlistItem.user_id, RuleSetRow)
        .join(RuleSetRow, RuleSetRow.user_id == WatchlistItem.user_id)
        .where(RuleSetRow.is_active.is_(True))
    )
    rows = (await session.execute(stmt)).all()
    return [(ticker, user_id, rule_set_to_domain(rs)) for ticker, user_id, rs in rows]


async def persist_catalyst(session: AsyncSession, catalyst: Catalyst) -> CatalystRow:
    """Upsert by external key so re-detection does not duplicate rows."""
    key = catalyst.id or (
        f"{catalyst.ticker}:{catalyst.type.value}:"
        f"{int(catalyst.window_expires_at.timestamp())}"
    )
    existing = await session.scalar(
        select(CatalystRow).where(CatalystRow.external_key == key)
    )
    if existing is not None:
        return existing

    row = CatalystRow(
        external_key=key,
        ticker=catalyst.ticker,
        type=catalyst.type.value,
        source=catalyst.source.value,
        direction=catalyst.direction.value,
        magnitude=catalyst.magnitude,
        materiality=catalyst.materiality,
        headline=catalyst.headline,
        payload=catalyst.payload,
        detected_at=catalyst.detected_at,
        window_expires_at=catalyst.window_expires_at,
    )
    session.add(row)
    await session.flush()
    return row


async def persist_alert(session: AsyncSession, alert: Alert) -> AlertRow:
    """Write an alert and open its outcome row.

    The outcome row is created immediately, with the horizon price still null.
    Every alert therefore has an outcome record from birth, which is what makes
    the table usable as a training set later.
    """
    catalyst_row = await persist_catalyst(session, alert.catalyst)

    row = AlertRow(
        user_id=alert.user_id,
        catalyst_id=catalyst_row.id,
        rule_set_id=alert.rule_set_id,
        ticker=alert.ticker,
        direction=alert.direction.value,
        confidence=alert.confidence,
        why=alert.why,
        catalyst_type=alert.catalyst.type.value,
        rule_tags=alert.confirmation.rule_tags,
        status=alert.status.value,
    )
    session.add(row)
    await session.flush()

    session.add(
        OutcomeRow(
            alert_id=row.id,
            horizon_minutes=15,
            price_at_alert=float(alert.catalyst.payload.get("price_at_alert", 0.0)),
        )
    )
    await session.flush()
    return row


def alert_to_payload(row: AlertRow) -> dict:
    """WebSocket payload. Field names match the Flutter Alert model."""
    return {
        "type": "alert",
        "data": {
            "id": row.id,
            "ticker": row.ticker,
            "direction": row.direction,
            "confidence": row.confidence,
            "why": row.why,
            "catalyst_type": row.catalyst_type,
            "rule_tags": row.rule_tags or [],
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        },
    }
