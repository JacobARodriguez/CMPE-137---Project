-- Confluence — reference PostgreSQL schema.
--
-- The application creates these tables itself via SQLAlchemy (`init_db()`), so
-- this file is documentation and a starting point for a DBA-managed deployment
-- rather than something the app executes. Keep it in step with
-- `app/db/models.py`, or adopt Alembic and let migrations be the source of truth.

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(320) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE watchlist_items (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker     VARCHAR(16) NOT NULL,
    sector     VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_watchlist_user_ticker UNIQUE (user_id, ticker)
);
CREATE INDEX ix_watchlist_ticker ON watchlist_items (ticker);

-- A user may save several profiles; exactly one is active and drives the
-- pipeline for that user.
CREATE TABLE rule_sets (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       VARCHAR(80) NOT NULL,
    combinator VARCHAR(8)  NOT NULL DEFAULT 'or',   -- 'and' | 'or'
    is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_rule_sets_user ON rule_sets (user_id);

CREATE TABLE rules (
    id          SERIAL PRIMARY KEY,
    rule_set_id INTEGER     NOT NULL REFERENCES rule_sets(id) ON DELETE CASCADE,
    type        VARCHAR(32) NOT NULL,   -- orb | ema_cross | volume_spike | vwap_reclaim
    params      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    enabled     BOOLEAN     NOT NULL DEFAULT TRUE
);
CREATE INDEX ix_rules_rule_set ON rules (rule_set_id);

-- Catalysts are shared across users -- detected once per ticker, not per user.
CREATE TABLE catalysts (
    id                SERIAL PRIMARY KEY,
    external_key      VARCHAR(255) NOT NULL UNIQUE,  -- idempotency on re-detection
    ticker            VARCHAR(16)  NOT NULL,
    type              VARCHAR(32)  NOT NULL,
    source            VARCHAR(32)  NOT NULL,
    direction         VARCHAR(8)   NOT NULL,
    magnitude         DOUBLE PRECISION NOT NULL,
    materiality       DOUBLE PRECISION,              -- text catalysts only
    headline          TEXT         NOT NULL,
    payload           JSONB        NOT NULL DEFAULT '{}'::jsonb,
    detected_at       TIMESTAMPTZ  NOT NULL,
    window_expires_at TIMESTAMPTZ  NOT NULL
);
CREATE INDEX ix_catalysts_ticker           ON catalysts (ticker);
CREATE INDEX ix_catalysts_ticker_detected  ON catalysts (ticker, detected_at);

CREATE TABLE alerts (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    catalyst_id   INTEGER     REFERENCES catalysts(id) ON DELETE SET NULL,
    rule_set_id   INTEGER     REFERENCES rule_sets(id) ON DELETE SET NULL,
    ticker        VARCHAR(16) NOT NULL,
    direction     VARCHAR(8)  NOT NULL,
    confidence    DOUBLE PRECISION NOT NULL,
    why           TEXT        NOT NULL,
    catalyst_type VARCHAR(32) NOT NULL,
    rule_tags     JSONB       NOT NULL DEFAULT '[]'::jsonb,
    status        VARCHAR(16) NOT NULL DEFAULT 'confirmed',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_alerts_user_created ON alerts (user_id, created_at);
CREATE INDEX ix_alerts_user_status  ON alerts (user_id, status);
CREATE INDEX ix_alerts_confidence   ON alerts (confidence);
CREATE INDEX ix_alerts_ticker       ON alerts (ticker);

-- Written for EVERY alert, with the horizon price filled in later. This is the
-- training set for the phase-2 ranking model, so completeness matters more than
-- keeping only the interesting rows.
CREATE TABLE outcomes (
    id               SERIAL PRIMARY KEY,
    alert_id         INTEGER     NOT NULL UNIQUE REFERENCES alerts(id) ON DELETE CASCADE,
    horizon_minutes  INTEGER     NOT NULL,
    price_at_alert   DOUBLE PRECISION NOT NULL,
    price_at_horizon DOUBLE PRECISION,
    move_pct         DOUBLE PRECISION,
    favorable        BOOLEAN,
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
