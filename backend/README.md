# Confluence — Backend

FastAPI service that detects fundamental catalysts, confirms them against
technical rules, ranks the survivors, and pushes them to the Flutter client.

## Quick start (no keys, no database, no Redis)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

python -m app.demo               # see the pipeline run offline
python -m pytest                 # 27 tests, all offline
uvicorn app.main:app --reload    # API on http://127.0.0.1:8000
```

Interactive API docs: <http://127.0.0.1:8000/docs>

With no `.env` at all the service runs on SQLite, an in-memory catalyst-window
store, and mock data providers. `GET /health` reports which implementation is
live for each provider, so mock-vs-real is never a guess.

## Layout

```
app/
  config.py        Settings; decides mock vs real per provider
  domain.py        Shared vocabulary (Bar, Catalyst, RuleSet, Alert, ...)
  security.py      PBKDF2 password hashing + JWT
  schemas.py       Pydantic API contract (mirrored by the Dart models)
  repository.py    DB <-> domain conversion; the queries the pipeline needs
  main.py          App, WebSocket channel, polling loop
  api/             Routes and dependencies
  db/              SQLAlchemy models and session management
  services/        External providers: Protocol + mock + real stub
  pipeline/        The six stages
    catalysts.py     1-3  ingest, score materiality, tag + open window
    rules.py         4    THE rule evaluator (live and backtest share it)
    indicators.py         EMA / VWAP / opening range / average volume
    ranking.py       5    heuristic ranker behind a swappable interface
    runner.py        6    orchestration and fan-out
    windows.py            confirmation-window state (Redis or in-memory)
    backtest.py           historical replay, no look-ahead
```

## Two invariants worth protecting

**One poll per ticker.** `PipelineRunner` fetches each ticker once per cycle and
fans results out to everyone watching it. Rule evaluation runs once per *distinct
rule set* (collapsed via `RuleSet.fingerprint()`), not once per user. `CycleReport`
exposes `duplicate_fetches`, which must always be 0; a test asserts it.

**One rule evaluator.** `evaluate_rule_set()` is called by both the live engine
and the backtester. The backtester passes `index=i` so only `bars[:i+1]` is
visible, which is what makes historical results honest. Never add rule logic
anywhere else — a second implementation is how a backtest starts lying.

## Configuration

Copy `.env.example` to `.env`. Everything is optional.

| Variable | Default | Effect |
|---|---|---|
| `DATABASE_URL` | SQLite file | Use `postgresql+asyncpg://...` in production (also `pip install -r requirements-postgres.txt`) |
| `REDIS_URL` | unset | Unset uses the in-memory window store |
| `SERVICE_MODE` | `auto` | `mock` forces mocks even when keys exist |
| `MATERIALITY_BACKEND` | `mock` | `claude` or `finbert` for real scoring |
| `POLL_INTERVAL_SECONDS` | 60 | Pipeline cycle period |
| `SECRET_KEY` | dev default | **Must** be changed outside dev |

Provider keys (`ALPACA_*`, `UNUSUAL_WHALES_*`, `FINNHUB_*`) select the real
implementation for that provider only when set.

## Status: what is and is not built

Built and tested: the full pipeline on mocks, rule engine, ranking, backtest,
auth, watchlist and rule-set CRUD, alert queries with filters, WebSocket push,
outcome logging.

**Not built — `app/services/real.py` raises `ServiceNotWired`.** Real provider
clients are the next milestone. Each stub records the endpoint and auth shape it
needs. They were deliberately not written blind: untested network code that
looks finished is worse than a stub that says what it is.

Also deliberately absent: broker execution (`PaperExecutionService` records
intent and contacts nothing), and the trained ranking model (`ModelRanker`
raises `NotImplementedError`; the `outcomes` table is its future training set).

## Dependencies

`requirements.txt` uses version **floors**, not exact pins. Exact pins to older
releases break on newer Python versions: pip cannot find a matching wheel, falls
back to a source build, and then needs Rust (for `pydantic-core`) or a C
compiler (for `asyncpg`). Floors let pip pick a release that has a wheel for
whatever interpreter you are on. Verified clean-install on Python 3.14.

Two extras are kept out of the default install on purpose:

| File | When you need it |
|---|---|
| `requirements-postgres.txt` | `asyncpg`, only when `DATABASE_URL` points at Postgres |
| `requirements-optional.txt` | `anthropic` or `transformers`, only for real materiality scoring |

If you want reproducible builds, generate a lockfile per environment with
`pip freeze > requirements.lock`.

## Migrations

`init_db()` runs `create_all` on startup, which creates missing tables but never
alters existing ones. Adopt Alembic before the schema changes under data you
care about.
