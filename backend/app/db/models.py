"""SQLAlchemy models.

Kept separate from `app.domain` on purpose: pipeline logic operates on plain
dataclasses and can be tested with no database at all. Conversion happens at the
API/persistence boundary.

JSON columns use JSONB on PostgreSQL (the production target) and plain JSON on
SQLite (the zero-setup dev default).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# JSONB where available, JSON elsewhere.
JSONVariant = JSON().with_variant(postgresql.JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    watchlist: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    rule_sets: Mapped[list["RuleSetRow"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
        Index("ix_watchlist_ticker", "ticker"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    ticker: Mapped[str] = mapped_column(String(16))
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="watchlist")


class RuleSetRow(Base):
    """A named, saved bundle of technical rules.

    Multiple saved profiles per user are supported; exactly one may be active,
    which is the one the pipeline uses for that user.
    """

    __tablename__ = "rule_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    combinator: Mapped[str] = mapped_column(String(8), default="or")  # "and" | "or"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="rule_sets")
    rules: Mapped[list["RuleRow"]] = relationship(
        back_populates="rule_set", cascade="all, delete-orphan", lazy="selectin"
    )


class RuleRow(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_set_id: Mapped[int] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(32))  # RuleType value
    params: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    rule_set: Mapped[RuleSetRow] = relationship(back_populates="rules")


class CatalystRow(Base):
    """A detected catalyst. Shared across users -- not per-user."""

    __tablename__ = "catalysts"
    __table_args__ = (
        Index("ix_catalysts_ticker_detected", "ticker", "detected_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    type: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(32))
    direction: Mapped[str] = mapped_column(String(8))
    magnitude: Mapped[float] = mapped_column(Float)
    materiality: Mapped[float | None] = mapped_column(Float, nullable=True)
    headline: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONVariant, default=dict)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertRow(Base):
    """A ranked signal delivered to one user."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_user_created", "user_id", "created_at"),
        Index("ix_alerts_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    catalyst_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalysts.id", ondelete="SET NULL"), nullable=True
    )
    rule_set_id: Mapped[int | None] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="SET NULL"), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    direction: Mapped[str] = mapped_column(String(8))
    confidence: Mapped[float] = mapped_column(Float, index=True)
    why: Mapped[str] = mapped_column(Text)
    catalyst_type: Mapped[str] = mapped_column(String(32), index=True)
    rule_tags: Mapped[list] = mapped_column(JSONVariant, default=list)
    status: Mapped[str] = mapped_column(String(16), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    outcome: Mapped["OutcomeRow | None"] = relationship(
        back_populates="alert", cascade="all, delete-orphan", uselist=False
    )


class OutcomeRow(Base):
    """What actually happened after an alert fired.

    Every alert gets a row here. This table is the training set for the phase-2
    ranking model, so it is written for all alerts, not just interesting ones.
    """

    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), unique=True, index=True
    )
    horizon_minutes: Mapped[int] = mapped_column(Integer)
    price_at_alert: Mapped[float] = mapped_column(Float)
    price_at_horizon: Mapped[float | None] = mapped_column(Float, nullable=True)
    move_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    favorable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    alert: Mapped[AlertRow] = relationship(back_populates="outcome")
