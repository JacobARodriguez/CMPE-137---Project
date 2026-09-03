"""Pydantic request/response models -- the API's public contract.

The Flutter client's Dart models mirror these field-for-field. Changing a field
name here is a breaking change for the app.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.domain import (
    AlertStatus,
    CatalystType,
    Combinator,
    Direction,
    RuleType,
)

# ----------------------------------------------------------------- auth ------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime


# ------------------------------------------------------------ watchlist ------


class WatchlistItemCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    sector: str | None = Field(default=None, max_length=64)


class WatchlistItemResponse(BaseModel):
    id: int
    ticker: str
    sector: str | None
    created_at: datetime


# ------------------------------------------------------------ rule sets ------


class RuleSpecPayload(BaseModel):
    type: RuleType
    params: dict = Field(default_factory=dict)
    enabled: bool = True


class RuleSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    combinator: Combinator = Combinator.OR
    rules: list[RuleSpecPayload] = Field(min_length=1)
    is_active: bool = True


class RuleSetResponse(BaseModel):
    id: int
    name: str
    combinator: Combinator
    is_active: bool
    rules: list[RuleSpecPayload]
    created_at: datetime


# --------------------------------------------------------------- alerts ------


class CatalystResponse(BaseModel):
    ticker: str
    type: CatalystType
    source: str
    direction: Direction
    magnitude: float
    materiality: float | None
    headline: str
    detected_at: datetime
    window_expires_at: datetime


class AlertResponse(BaseModel):
    """One dashboard card."""

    id: int
    ticker: str
    direction: Direction
    confidence: float
    why: str
    catalyst_type: CatalystType
    rule_tags: list[str]
    status: AlertStatus
    created_at: datetime


class AlertFilters(BaseModel):
    """Dashboard filter state. Mirrors the Flutter filter bar."""

    tickers: list[str] | None = None
    catalyst_types: list[CatalystType] | None = None
    direction: Direction | None = None
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confirmed_only: bool = True
    sort_by: str = Field(default="confidence", pattern="^(confidence|recency)$")
    limit: int = Field(default=100, ge=1, le=500)


# ------------------------------------------------------------- backtest ------


class BacktestRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    rule_set_id: int
    direction: Direction = Direction.BULLISH
    horizon_bars: int = Field(default=15, ge=1, le=200)
    bars: int = Field(default=200, ge=50, le=2000)


class BacktestSignalResponse(BaseModel):
    index: int
    bar_ts: str
    entry_price: float
    exit_price: float
    move_pct: float
    favorable: bool
    rule_tags: list[str]


class BacktestResponse(BaseModel):
    ticker: str
    direction: Direction
    horizon_bars: int
    bars_tested: int
    signal_count: int
    hit_rate: float
    average_move_pct: float
    signals: list[BacktestSignalResponse]


# --------------------------------------------------------------- system ------


class HealthResponse(BaseModel):
    status: str
    environment: str
    services: dict[str, str]
    window_store: str
