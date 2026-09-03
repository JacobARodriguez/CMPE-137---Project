# CMPE 137 Project

## Overview

This project is a mobile software engineering application for short-term equity traders. It monitors a personalized watchlist for potentially meaningful company and market catalysts, analyzes those events, and waits for user-configured technical confirmation before generating a high-priority alert.

The central idea is that a catalyst by itself is not necessarily actionable, and a technical signal by itself may also be noisy. The system combines both layers so that a confirmed alert explains what happened, how the event was interpreted, and which technical conditions confirmed the market reaction.

The mobile application is being developed with Dart and Flutter. The initial architecture is intended to use a Flutter client, a Python/Flask backend, and PostgreSQL for persistent data. The system is organized as a modular monolith so the semester implementation remains manageable while still leaving clear extension points for later features.

## Development Methodology

Development follows a modified Agile workflow intended for a two-person team and a semester-length project.

Work is divided into short, incremental sprints. Each sprint should end with a visible and testable improvement to the application rather than a large collection of unfinished components.

The general sprint cycle is:

1. **Sprint Planning** — choose the user stories and technical tasks that will be worked on during the sprint.
2. **Sprint Work** — implement, test, document, and integrate the selected work.
3. **Sprint Review** — demonstrate the working result of the sprint and compare it against the selected user stories.
4. **Sprint Retrospective** — discuss what worked, what caused delays or confusion, and what should change in the next sprint.
5. **Backlog Update** — revise priorities and prepare the next set of work based on the current state of the project.

User stories are used to describe planned functionality, but story points are not required. Progress can instead be tracked with completed and remaining work using a burn-down or burn-up view when useful.

Because the team is small, communication and integration should remain lightweight. Tasks should still be clearly assigned, branches should remain focused, and completed work should be reviewed before being merged into the main branch.

## Core User Workflow

The high-level application workflow is:

```text
Build watchlist
      ↓
Monitor data sources
      ↓
Detect catalyst
      ↓
Extract relevant information
      ↓
AI/NLP materiality analysis when applicable
      ↓
Evaluate context and candidate direction
      ↓
Open confirmation window
      ↓
Check user-configured technical rules
      ↓
Generate confirmed alert
      ↓
Review and act
      ↓
Log outcome
      ↓
Use results for historical analysis
```

The order above describes the general flow of information through the application. Individual features may run concurrently or be implemented in a different sprint order.

## Catalyst and Direction Workflow

Catalysts should not be reduced to simplistic rules such as "earnings beat = bullish" or "call activity = bullish."

The intended flow is:

```text
Raw event
   ↓
Extract event features
   ↓
AI/NLP materiality analysis when applicable
   ↓
Evaluate surrounding context
   ↓
Assign candidate directional bias
   ↓
Open confirmation window
   ↓
Technical rules validate, contradict, or fail to confirm the bias
```

For example, an earnings beat accompanied by a major guidance cut should be handled differently from a clean earnings beat. Structured events such as earnings numbers, insider transactions, and options activity may require little or no NLP processing, while text-heavy events such as 8-K filings, press releases, and news articles are candidates for model-based materiality analysis.

## Confirmation Workflow

The confirmation engine is responsible for determining whether market behavior supports a detected catalyst.

```text
Catalyst detected
      ↓
Open confirmation window
      ↓
Evaluate incoming market data
      ↓
Check configured technical rules
      ↓
Does a rule match within the window?
      /                         \
    Yes                         No
     ↓                           ↓
Confirmed alert             Window expires
```

A catalyst can therefore exist without producing a confirmed alert. The system only generates the confirmed alert when the configured technical conditions are satisfied within the allowed confirmation window and are consistent with the event context.

The same rule-evaluation logic should be reusable for both live confirmation and historical backtesting whenever practical.

## Feature Roadmap

### Core MVP

The priority is to complete as much of the end-to-end workflow as possible while keeping the system demonstrable at every stage.

- Personalized watchlist
- Insider cluster-buy detector using SEC Form 4 data
- Earnings surprise and guidance-change detector
- Unusual options volume/open-interest anomaly detector
- AI/NLP materiality scoring for 8-K filings and relevant news
- Context-aware candidate directional bias
- Configurable technical rules, including:
  - Opening Range Breakout parameters
  - EMA periods and cross conditions
  - Volume-spike threshold
  - VWAP reclaim conditions
- Confirmed-alert engine combining catalyst and technical confirmation
- Plain-language explanation of why an alert was generated
- Push notifications
- Historical outcome logging

### Strong Secondary Goal

- Historical backtest view
- Hit rate by symbol and rule combination
- Average move following a confirmed signal
- Multiple saved rule-set profiles for different strategies, sectors, or setups

### MVP Stretch Goal

Paper trading is considered part of the intended MVP direction, but it should only be implemented after the alert pipeline is working reliably.

- Broker connection with paper-trading mode first
- User-defined paper-execution rules tied to confirmed alerts
- Position size, stop, and target configuration
- Daily loss-limit and maximum-position guardrails

The goal is to progress as far into this section as the semester schedule reasonably allows without sacrificing the stability of the core pipeline.

### Experimental / Later Technical Work

- Evaluate Kronos or a similar financial time-series foundation model as an additional technical signal
- Use model output as an input to the broader confirmation/ranking system rather than replacing the rule-based confirmation engine by default
- Train a later fusion/ranking model on historical catalyst-confirmation outcomes if enough reliable data becomes available

### Business / Product Roadmap

The following ideas remain theoretical or optional for the semester implementation:

- Subscription tiers and watchlist limits by account tier
- Premium alert sensitivity controls
- Expanded broker integrations
- Full discretionary automation after appropriate legal and compliance review
- Aggregated anonymized signal-performance data for possible licensing use

These features should not interfere with completion of the core system.

## AI and NLP Strategy

The project is intended to use an actual AI/NLP model for materiality analysis rather than relying only on manually written heuristics.

The model should be used primarily for text-heavy events such as:

- 8-K filings
- Press releases
- Relevant company news
- Guidance statements
- Earnings-call or management commentary when available

Heuristics may still be useful for preprocessing, fallback behavior, filtering, or structured event handling, but they are not intended to replace the AI/NLP component.

The exact model is not permanently fixed at this stage. Candidate approaches may include a financial-domain language model such as FinBERT or another suitable NLP model after evaluation.

Model outputs should be treated as one input into the event-processing pipeline rather than as an unquestioned buy/sell decision.

## Future Model Strategy

Kronos is a possible later addition if it proves practical for the project.

The initial technical confirmation engine should remain based on transparent user-configured rules such as ORB, EMA, VWAP, and volume conditions. Kronos can later be evaluated as an additional signal or feature source.

A future ranking or fusion model may use features such as:

- Catalyst type and magnitude
- AI/NLP materiality score
- Technical strength at confirmation
- Market and sector context
- Liquidity and volatility
- Historical performance of similar catalyst-rule combinations

Any future probability, confidence, or hit-rate values shown in the application should come from real model outputs or measured historical data. Example percentages used during planning are not design requirements.

## Data Sources and API Strategy

The backend should be responsible for external financial-data access rather than allowing each mobile client to call vendor APIs independently.

This allows the system to:

- Poll or subscribe to a symbol once
- Normalize data centrally
- Run catalyst and confirmation logic once
- Cache reusable results
- Reduce API usage and cost
- Fan relevant results out to users watching the same symbol

The architecture should support the following data-provider categories:

- Market price and volume data
- Company news
- SEC filings
- Earnings data
- Options activity
- Broker/paper-trading access

Specific vendors will be evaluated later based on API coverage, pricing, rate limits, licensing, reliability, and development complexity. The repository should avoid tightly coupling the application to a provider before that evaluation is complete.

## Dashboard Filtering

Alerts stored by the backend should carry enough metadata to support filtering without recomputing the signal.

Planned dashboard filters include:

- Watchlist or ticker
- Catalyst type
- Direction
- Rule-set or strategy profile
- Time range
- Confidence or historical-performance threshold when meaningful measured values become available

Planned sorting options may include:

- Most recent first
- Highest measured confidence or historical performance first
- Largest expected or historical move when supported by real data

The dashboard may also distinguish between:

- **Confirmed alerts** — catalyst and technical conditions have aligned
- **Pending catalysts** — an event has been detected but has not yet received technical confirmation

Pending catalysts may be visually muted so they provide context without being confused with confirmed alerts.

## System Architecture

The application is organized as a modular monolith.

```text
Flutter Mobile Application
        Dart Client
            │
            │ REST API
            ▼
┌───────────────────────────────┐
│          Flask Backend        │
│                               │
│ authentication                │
│ watchlists                    │
│ rules                         │
│ provider adapters             │
│ market data                   │
│ catalysts                     │
│ AI/NLP scoring                │
│ context/direction analysis    │
│ confirmation                  │
│ alerts                        │
│ notifications                 │
│ backtests                     │
│ paper trading                 │
│ background jobs               │
└───────────────┬───────────────┘
                │
                ▼
           PostgreSQL
```

The backend is separated by responsibility rather than by deploying each feature as a separate service. This keeps the project easier to develop, test, and deploy while preserving clean module boundaries.

## Backend Responsibilities

### Watchlists

Stores the symbols a user wants the system to monitor. Account-tier limits may be added later if the business-model portion of the project is implemented.

### Provider Adapters

Isolate third-party API details from the rest of the application so market/news/filing providers can be evaluated or replaced without rewriting core business logic.

### Market Data

Provides normalized price, volume, options, earnings, filing, and news data to the rest of the application.

### Catalysts

Answers the question:

> Did something potentially significant happen?

Initial catalyst modules include:

- Insider activity
- Earnings and guidance
- Options anomalies
- SEC filings and relevant news

### AI/NLP Materiality Scoring

Analyzes text-heavy events and ranks their estimated importance so low-value events do not receive the same treatment as events more likely to affect the market.

### Context and Direction Analysis

Combines extracted event details with surrounding context to determine a candidate directional bias without relying on one-line assumptions about catalyst direction.

### Confirmation

Answers the question:

> Is the market behaving according to the user's configured strategy?

Initial confirmation rules include:

- Opening Range Breakout
- EMA conditions and crosses
- Volume spikes
- VWAP reclaim

### Alerts

Answers the question:

> Is there enough evidence to notify the user?

A confirmed alert should include both the catalyst and the technical condition that confirmed it.

### Notifications

Delivers confirmed alerts to the user through supported notification channels.

### Backtesting

Stores and evaluates historical outcomes so the application can report signal performance by symbol, rule, or rule profile.

### Paper Trading

If reached during the semester, routes user-defined simulated execution rules through a supported paper-trading broker connection while preserving risk guardrails.

### Background Jobs

Many project features operate without a direct user request. Scheduled or background jobs may be responsible for tasks such as:

- Polling SEC filings
- Checking earnings data
- Updating market data
- Scanning options activity
- Processing relevant news
- Running AI/NLP analysis
- Evaluating active confirmation windows
- Expiring confirmation windows
- Updating historical alert outcomes

## Proposed Repository Structure

```text
CMPE-137---Project/
│
├── README.md
├── CONTRIBUTING.md
├── .gitignore
├── .env.example
├── docker-compose.yml
│
├── .github/
│   ├── workflows/
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
│
├── mobile/
│   ├── pubspec.yaml
│   ├── analysis_options.yaml
│   ├── test/
│   └── lib/
│       ├── main.dart
│       ├── screens/
│       ├── widgets/
│       ├── services/
│       ├── models/
│       ├── providers/
│       └── utils/
│
├── backend/
│   ├── auth/
│   ├── users/
│   ├── watchlists/
│   ├── rules/
│   ├── providers/
│   ├── market_data/
│   ├── catalysts/
│   │   ├── insider/
│   │   ├── earnings/
│   │   ├── options/
│   │   └── filings/
│   ├── scoring/
│   ├── context/
│   ├── confirmation/
│   ├── alerts/
│   ├── notifications/
│   ├── backtests/
│   ├── paper_trading/
│   ├── jobs/
│   ├── db/
│   └── tests/
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── database.md
│   ├── development-cycle.md
│   └── feature-roadmap.md
│
└── scripts/
```

Folders should be added when implementation begins rather than creating unused modules only to match the long-term roadmap.

## Suggested Mobile Screens

The Flutter application is expected to grow around the following screens:

- Dashboard
- Watchlist
- Alerts
- Alert Details
- Technical Rules
- Backtest Results
- Settings
- Profile

Reusable Flutter widgets may include ticker cards, alert cards, catalyst indicators, technical-confirmation summaries, rule editors, and charts.

## Technology Stack

### Mobile Application

- Dart
- Flutter

### Backend

- Python
- Flask

### Database

- PostgreSQL

### AI / Machine Learning

- Financial NLP model for materiality analysis
- Kronos evaluation as a later experimental technical signal if practical
- Future ranking/fusion model only after sufficient reliable data exists

### Development and Deployment

- Docker
- Docker Compose
- GitHub

### Testing

- Flutter test framework for mobile unit and widget testing
- Pytest for backend testing
- Integration testing where appropriate
- Historical validation for signal-processing logic where appropriate

## Development References

The following official documentation should be used as the primary reference for Dart and Flutter implementation decisions:

- [Dart Language Documentation](https://dart.dev/language)
- [Flutter Documentation](https://docs.flutter.dev/)

These references cover Dart language features, Flutter widgets, application structure, navigation, platform setup, testing, and deployment guidance.

## Git Workflow

The `main` branch should represent the latest stable, integrated version of the project.

Development work should normally occur on focused branches. Example naming conventions include:

```text
feature/watchlist-ui
feature/insider-detector
feature/orb-confirmation
feature/materiality-model
fix/alert-duplicate
refactor/market-data-service
```

A typical development flow is:

```text
Create or select user story
        ↓
Create focused branch
        ↓
Implement and test
        ↓
Push branch
        ↓
Open pull request
        ↓
Partner review
        ↓
Resolve issues
        ↓
Merge into main
```

Pull requests should remain small enough to review without requiring the reviewer to understand several unrelated features at once.

## User Stories

Features should be represented as user stories whenever practical.

Example:

```text
As a user,
I want to configure an EMA confirmation rule,
so that alerts are only generated when the market meets my strategy conditions.
```

A user story is considered complete when its acceptance criteria are satisfied and the feature is integrated into the current application.

## Definition of Done

Unless a sprint specifies otherwise, work should not be treated as complete only because the code has been written.

A feature is considered done when:

- The intended behavior is implemented
- Acceptance criteria are satisfied
- Relevant tests pass
- Existing functionality has not been knowingly broken
- Required configuration is documented
- No secrets or private credentials are committed
- The code is integrated with the current project
- The partner has had an opportunity to review the change
- The feature can be demonstrated during the sprint review

## Sprint Reviews and Retrospectives

At the end of each sprint, the current working software should be reviewed against the planned user stories.

The review focuses on what was completed and what can be demonstrated.

The retrospective focuses on the development process itself, including:

- What worked well
- What slowed the team down
- Integration problems
- Communication problems
- Testing problems
- Changes that should be made during the next sprint

The results of the retrospective should influence the next sprint rather than being treated only as documentation.

## Progress Tracking

A burn-down or burn-up chart may be used to show sprint or project progress.

A burn-down chart tracks remaining work over time. A burn-up chart tracks completed work toward the current project scope.

These charts are project-tracking tools rather than separate Agile meetings. They may be reviewed during sprint work, planning, reviews, or other team check-ins.

## Configuration and Secrets

API keys, database passwords, authentication secrets, broker credentials, and other sensitive configuration must not be committed to the repository.

Development configuration should be represented in `.env.example` with placeholder values. Each developer should maintain a local `.env` file containing actual credentials.

## Scope Management

The primary goal is a working end-to-end system, not implementation of every long-term feature.

The development order may change as APIs are evaluated, technical risks are discovered, or integration work becomes necessary. Features should be prioritized according to their value to the central workflow:

```text
Watchlist
   ↓
Data ingestion
   ↓
Catalyst detection
   ↓
AI/NLP materiality analysis
   ↓
Context and direction assessment
   ↓
Technical confirmation
   ↓
Confirmed alert
   ↓
Historical outcome/backtest
   ↓
Paper trading if time permits
```

A smaller complete workflow is preferred over a larger collection of disconnected features.

## Current Status

The repository is currently in the project setup and early implementation phase. A Flutter/Dart scaffold is present under `mobile/`, and the project architecture, Agile workflow, feature roadmap, and development conventions are documented.

Initial implementation work should focus on establishing the backend foundations, provider abstraction, database structure, and one complete vertical path from watchlist data through catalyst detection, materiality analysis, technical confirmation, and alert generation before expanding the number of detectors or attempting paper trading and experimental models.