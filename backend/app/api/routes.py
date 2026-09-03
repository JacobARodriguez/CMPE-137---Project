"""HTTP routes: auth, watchlist, rule sets, alerts, backtest."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import Settings, get_settings
from app.db.models import AlertRow, RuleRow, RuleSetRow, User, WatchlistItem
from app.db.session import get_session
from app.domain import CatalystType, Direction
from app.pipeline.backtest import run_backtest
from app.repository import rule_set_to_domain
from app.schemas import (
    AlertResponse,
    BacktestRequest,
    BacktestResponse,
    LoginRequest,
    RegisterRequest,
    RuleSetCreate,
    RuleSetResponse,
    RuleSpecPayload,
    TokenResponse,
    UserResponse,
    WatchlistItemCreate,
    WatchlistItemResponse,
)
from app.security import create_access_token, hash_password, verify_password
from app.services.registry import build_services

router = APIRouter()

# ------------------------------------------------------------------ auth -----

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    existing = await session.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(email=body.email, hashed_password=hash_password(body.password))
    session.add(user)
    await session.flush()

    # Give every new account a sensible starting rule set so the dashboard is
    # not empty on first login.
    default_set = RuleSetRow(user_id=user.id, name="Default", combinator="or")
    default_set.rules = [
        RuleRow(type="orb", params={"minutes": 15, "threshold_pct": 0.1}),
        RuleRow(type="ema_cross", params={"fast": 9, "slow": 21}),
        RuleRow(type="volume_spike", params={"lookback": 20, "multiple": 2.0}),
        RuleRow(type="vwap_reclaim", params={"lookback": 30}),
    ]
    session.add(default_set)
    await session.commit()

    return TokenResponse(
        access_token=create_access_token(
            user.id, settings.secret_key, settings.access_token_ttl_minutes
        )
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(
            user.id, settings.secret_key, settings.access_token_ttl_minutes
        )
    )


@auth_router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, created_at=user.created_at)


# ------------------------------------------------------------- watchlist -----

watchlist_router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@watchlist_router.get("", response_model=list[WatchlistItemResponse])
async def list_watchlist(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[WatchlistItemResponse]:
    rows = await session.scalars(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.ticker)
    )
    return [
        WatchlistItemResponse(
            id=r.id, ticker=r.ticker, sector=r.sector, created_at=r.created_at
        )
        for r in rows
    ]


@watchlist_router.post("", response_model=WatchlistItemResponse, status_code=201)
async def add_to_watchlist(
    body: WatchlistItemCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WatchlistItemResponse:
    ticker = body.ticker.strip().upper()
    existing = await session.scalar(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user.id, WatchlistItem.ticker == ticker
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{ticker} already watched")

    item = WatchlistItem(user_id=user.id, ticker=ticker, sector=body.sector)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return WatchlistItemResponse(
        id=item.id, ticker=item.ticker, sector=item.sector, created_at=item.created_at
    )


@watchlist_router.delete("/{ticker}", status_code=204)
async def remove_from_watchlist(
    ticker: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.execute(
        delete(WatchlistItem).where(
            WatchlistItem.user_id == user.id,
            WatchlistItem.ticker == ticker.strip().upper(),
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not on watchlist")
    await session.commit()


# ------------------------------------------------------------- rule sets -----

rules_router = APIRouter(prefix="/rule-sets", tags=["rule-sets"])


def _rule_set_to_response(row: RuleSetRow) -> RuleSetResponse:
    return RuleSetResponse(
        id=row.id,
        name=row.name,
        combinator=row.combinator,
        is_active=row.is_active,
        created_at=row.created_at,
        rules=[
            RuleSpecPayload(type=r.type, params=r.params or {}, enabled=r.enabled)
            for r in row.rules
        ],
    )


@rules_router.get("", response_model=list[RuleSetResponse])
async def list_rule_sets(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[RuleSetResponse]:
    rows = await session.scalars(
        select(RuleSetRow).where(RuleSetRow.user_id == user.id).order_by(RuleSetRow.id)
    )
    return [_rule_set_to_response(r) for r in rows]


@rules_router.post("", response_model=RuleSetResponse, status_code=201)
async def create_rule_set(
    body: RuleSetCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RuleSetResponse:
    if body.is_active:
        # Exactly one active profile per user -- the pipeline reads that one.
        for other in await session.scalars(
            select(RuleSetRow).where(
                RuleSetRow.user_id == user.id, RuleSetRow.is_active.is_(True)
            )
        ):
            other.is_active = False

    row = RuleSetRow(
        user_id=user.id,
        name=body.name,
        combinator=body.combinator.value,
        is_active=body.is_active,
    )
    row.rules = [
        RuleRow(type=r.type.value, params=r.params, enabled=r.enabled)
        for r in body.rules
    ]
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _rule_set_to_response(row)


@rules_router.post("/{rule_set_id}/activate", response_model=RuleSetResponse)
async def activate_rule_set(
    rule_set_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RuleSetResponse:
    target = await session.scalar(
        select(RuleSetRow).where(
            RuleSetRow.id == rule_set_id, RuleSetRow.user_id == user.id
        )
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule set not found")

    for other in await session.scalars(
        select(RuleSetRow).where(RuleSetRow.user_id == user.id)
    ):
        other.is_active = other.id == rule_set_id
    await session.commit()
    await session.refresh(target)
    return _rule_set_to_response(target)


@rules_router.delete("/{rule_set_id}", status_code=204)
async def delete_rule_set(
    rule_set_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.execute(
        delete(RuleSetRow).where(
            RuleSetRow.id == rule_set_id, RuleSetRow.user_id == user.id
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule set not found")
    await session.commit()


# ---------------------------------------------------------------- alerts -----

alerts_router = APIRouter(prefix="/alerts", tags=["alerts"])


@alerts_router.get("", response_model=list[AlertResponse])
async def list_alerts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    tickers: list[str] | None = Query(default=None),
    catalyst_types: list[CatalystType] | None = Query(default=None),
    direction: Direction | None = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    confirmed_only: bool = Query(default=True),
    sort_by: str = Query(default="confidence", pattern="^(confidence|recency)$"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AlertResponse]:
    """The dashboard's main query. Filters mirror the Flutter filter bar."""
    stmt = select(AlertRow).where(AlertRow.user_id == user.id)

    if tickers:
        stmt = stmt.where(AlertRow.ticker.in_([t.strip().upper() for t in tickers]))
    if catalyst_types:
        stmt = stmt.where(AlertRow.catalyst_type.in_([c.value for c in catalyst_types]))
    if direction is not None:
        stmt = stmt.where(AlertRow.direction == direction.value)
    if min_confidence > 0:
        stmt = stmt.where(AlertRow.confidence >= min_confidence)
    if confirmed_only:
        stmt = stmt.where(AlertRow.status == "confirmed")

    order = AlertRow.confidence if sort_by == "confidence" else AlertRow.created_at
    stmt = stmt.order_by(order.desc()).limit(limit)

    rows = await session.scalars(stmt)
    return [
        AlertResponse(
            id=r.id,
            ticker=r.ticker,
            direction=r.direction,
            confidence=r.confidence,
            why=r.why,
            catalyst_type=r.catalyst_type,
            rule_tags=r.rule_tags or [],
            status=r.status,
            created_at=r.created_at,
        )
        for r in rows
    ]


# -------------------------------------------------------------- backtest -----

backtest_router = APIRouter(prefix="/backtest", tags=["backtest"])


@backtest_router.post("", response_model=BacktestResponse)
async def backtest(
    body: BacktestRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> BacktestResponse:
    """Replay a saved rule set over historical bars.

    Uses the same `evaluate_rule_set` the live engine uses, so results describe
    the rules the user is actually running.
    """
    row = await session.scalar(
        select(RuleSetRow).where(
            RuleSetRow.id == body.rule_set_id, RuleSetRow.user_id == user.id
        )
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule set not found")

    services = build_services(settings)
    bars = await services.market_data.get_bars(body.ticker.strip().upper(), body.bars)
    result = run_backtest(
        body.ticker.strip().upper(),
        bars,
        rule_set_to_domain(row),
        body.direction,
        horizon_bars=body.horizon_bars,
    )
    return BacktestResponse(**result.to_dict())


router.include_router(auth_router)
router.include_router(watchlist_router)
router.include_router(rules_router)
router.include_router(alerts_router)
router.include_router(backtest_router)
