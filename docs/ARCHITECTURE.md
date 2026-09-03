# Confluence — Architecture

Confluence surfaces short-term trade signals. A **confirmed alert** fires only
when a *fundamental catalyst* and a *technical confirmation* align for a
watchlisted ticker inside a time window. Everything else is discarded silently.

```
                        ┌────────────────────────────────────┐
   Alpaca ─┐            │            BACKEND                 │
   UW   ───┼─ once per  │                                    │
   Finnhub ┤   ticker   │  1 ingest ──> 2 materiality ──>    │
   EDGAR ──┘  ────────> │  3 tag + open window ──>           │
                        │  4 confirm (per distinct rule set) │
                        │  5 rank ──> 6 push + log           │
                        └───────┬──────────────────┬─────────┘
                                │ WebSocket        │ PostgreSQL
                                v                  v
                        Flutter dashboard      alerts + outcomes
```

## The rule that shapes everything

> Poll each watchlisted ticker **once** per interval, run the catalyst pipeline
> **once**, and fan the results out to every user watching it.

Clients never touch an external API. Cost scales with *tickers*, not *users*.

Confirmation is the subtle part, because technical rules are per-user
configurable while the expensive work is not:

| Work | Frequency | Why |
|---|---|---|
| External I/O (bars, news, flow, filings) | once per **ticker** | The expensive part |
| Catalyst detection | once per **ticker** | Depends only on ticker data |
| Rule evaluation | once per **distinct rule set** | Pure local maths over fetched bars |
| Alert delivery | per **user** | Each watcher gets their own row |

Identical rule sets collapse via `RuleSet.fingerprint()`, so 25 users on the
default profile cause **one** evaluation. `CycleReport.duplicate_fetches` must
always be 0 and is asserted in the test suite.

## The six stages

1. **Ingest** — `pipeline/catalysts.py::detect_catalysts` fans out across every
   provider concurrently. One provider failing loses only its own catalysts.
2. **Score materiality** — text only (8-K, press release, transcript). Numeric
   catalysts carry their own magnitude and skip this step entirely:

   | Catalyst | Magnitude from | Scored? |
   |---|---|---|
   | Earnings surprise | EPS surprise % | no |
   | Insider buy/sell | dollar value | no |
   | Options flow | premium | no |
   | 8-K / news | materiality model | **yes** |

3. **Tag** — assign direction and magnitude, open a confirmation window whose
   duration depends on catalyst type (options 30m, earnings 60m, news 90m,
   8-K 120m, insider 24h).
4. **Confirm** — on new bars, evaluate the user's rules. **Direction must
   match**: a bullish catalyst is never confirmed by a bearish breakout. Nothing
   fires before the window expires → discarded silently.
5. **Rank** — weighted heuristic over catalyst class, magnitude, rule agreement,
   and freshness, behind a `Ranker` protocol so a trained model can replace it.
6. **Push + log** — WebSocket to the dashboard; every alert plus its later
   outcome is written to `outcomes`, which becomes the training set.

## One rule evaluator, two callers

`pipeline/rules.py::evaluate_rule_set(bars, rule_set, direction, index)` is the
only place a rule is interpreted.

- **Live**: called with the newest bars.
- **Backtest**: called in a loop with `index=i`, which restricts it to
  `bars[:i+1]`.

That `index` parameter is the no-look-ahead guarantee, and it is tested three
ways: an early index sees no signal, appending future bars never changes a past
evaluation, and no signal is scored without a full forward horizon available.

Adding rule logic anywhere else is how a backtest starts lying about the rules
you are actually running.

## Data model

`users` → `watchlist_items`, `rule_sets` → `rules`. Detected `catalysts` are
shared across users; `alerts` are per user and reference the catalyst that
caused them; every alert gets an `outcomes` row at birth.

## Deliberate non-goals

| Not built | Where the seam is |
|---|---|
| Broker execution / auto-trading | `ExecutionService`; `PaperExecutionService` records intent and contacts nothing |
| Trained ML ranker | `Ranker` protocol; `ModelRanker` raises `NotImplementedError` |
| Real provider clients | `services/real.py` raises `ServiceNotWired` with the endpoint documented |

Confluence does not place discretionary trades. Any future execution must be
user-preconfigured rules routed through a licensed broker.

## Offline-first

The entire pipeline runs with **no keys, no PostgreSQL, and no Redis**: mock
providers, SQLite, and an in-memory window store. That is what the 27 backend
tests and `python -m app.demo` exercise, and it means a teammate can clone the
repo and see the system work before obtaining a single API key.
