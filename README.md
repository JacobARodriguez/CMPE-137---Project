# CMPE 137 Project

## Overview

This project is a mobile software engineering application focused on detecting potentially significant market events and confirming those events with user-configured technical trading rules before generating an alert.

The application is designed around a simple idea: a catalyst by itself is not necessarily actionable. The system first detects a potentially meaningful event, then watches market behavior for technical confirmation. A confirmed alert combines both pieces of information so the user can see what happened and why the system considers the market reaction significant.

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
Monitor catalysts
      ↓
Check technical confirmation
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

A catalyst can therefore exist without producing a confirmed alert. The system only generates the confirmed alert when the configured technical conditions are satisfied within the allowed confirmation window.

## Feature Roadmap

### Core MVP — Weeks 1–13

- Personalized watchlist with ticker limits that can scale by account tier
- Insider cluster-buy detector using SEC Form 4 data
- Earnings surprise and guidance-change detector
- Unusual options volume/open-interest anomaly detector
- Materiality scoring for 8-K filings and relevant news
- Configurable technical rules, including:
  - Opening Range Breakout parameters
  - EMA periods and cross conditions
  - Volume-spike threshold
  - VWAP reclaim conditions
- Confirmed-alert engine combining catalyst and technical confirmation
- Plain-language explanation of why an alert was generated
- Push notifications

### Near-Launch — Weeks 9–14

- Historical backtest view
- Hit rate by symbol and rule combination
- Average move following a confirmed signal
- Multiple saved rule-set profiles for different strategies, sectors, or setups

These features may begin before all core work is complete when doing so supports incremental testing or reduces later integration risk.

### Premium / Phase 2

- Broker connection with paper trading first
- User-defined auto-execution rules
- Position size, stop, and target configuration
- Daily loss limit
- Maximum position guardrails
- Alert sensitivity tuning

### Later Roadmap

- Full discretionary automation after appropriate legal and compliance review
- Aggregated anonymized signal-performance data for possible licensing use

The premium and later-roadmap features are not required for the initial semester implementation and should not interfere with completing a stable MVP.

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
│ market data                   │
│ catalysts                     │
│ materiality scoring           │
│ confirmation                  │
│ alerts                        │
│ notifications                 │
│ backtests                     │
│ background jobs               │
└───────────────┬───────────────┘
                │
                ▼
           PostgreSQL
```

The backend is separated by responsibility rather than by deploying each feature as a separate service. This keeps the project easier to develop, test, and deploy while preserving clean module boundaries.

## Backend Responsibilities

### Watchlists

Stores the symbols a user wants the system to monitor and manages any account-tier limits.

### Market Data

Provides normalized price, volume, options, earnings, and filing data to the rest of the application.

### Catalysts

Answers the question:

> Did something potentially significant happen?

Initial catalyst modules include:

- Insider activity
- Earnings and guidance
- Options anomalies
- SEC filings and relevant news

### Materiality Scoring

Ranks filings and news by estimated importance so low-value events do not receive the same treatment as events likely to affect the market.

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

### Background Jobs

Many project features operate without a direct user request. Scheduled or background jobs may be responsible for tasks such as:

- Polling SEC filings
- Checking earnings data
- Updating market data
- Scanning options activity
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
│   ├── android/
│   ├── ios/
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
│   ├── market_data/
│   ├── catalysts/
│   │   ├── insider/
│   │   ├── earnings/
│   │   ├── options/
│   │   └── filings/
│   ├── scoring/
│   ├── confirmation/
│   ├── alerts/
│   ├── notifications/
│   ├── backtests/
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

### Development and Deployment

- Docker
- Docker Compose
- GitHub

### Testing

- Flutter test framework for mobile unit and widget testing
- Pytest for backend testing
- Integration testing where appropriate

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

The primary goal is a working MVP, not implementation of the entire long-term roadmap.

The development order may change as APIs are evaluated, technical risks are discovered, or integration work becomes necessary. Features should be prioritized according to their value to the central workflow:

```text
Watchlist → Catalyst → Confirmation → Alert → Outcome
```

A smaller complete workflow is preferred over a larger collection of disconnected features.

## Current Status

The repository is currently in the project setup and architecture phase. Initial work should focus on establishing the Flutter mobile application and backend foundations, development workflow, database structure, and one complete vertical feature path before expanding the number of detectors and technical rules.
