# Contributing

## Team Workflow

Development follows a lightweight modified Agile process for a two-person team. Work should be planned in short sprints and integrated frequently so each sprint ends with a working, demonstrable improvement.

## Before Starting Work

1. Select a user story or clearly defined technical task from the current sprint.
2. Confirm that the task is not already being worked on by the other team member.
3. Create a focused branch from the latest `main` branch.
4. Keep the branch limited to the selected feature, fix, or refactor whenever possible.

Example branch names:

```text
feature/watchlist-ui
feature/insider-detector
feature/orb-confirmation
fix/alert-duplicate
refactor/market-data-service
```

## Commits

Commits should describe the change being made and remain reasonably focused.

Examples:

```text
Add watchlist API endpoint
Implement EMA confirmation rule
Fix duplicate confirmed alerts
Add tests for SEC filing parser
```

Large unrelated changes should not be bundled into a single commit when they can be separated cleanly.

## Pull Requests

Completed work should normally be merged through a pull request.

A pull request should include:

- A short description of what changed
- The user story or task being addressed
- How the change was tested
- Any known limitations or follow-up work
- Screenshots when a user-interface change benefits from visual review

The other team member should review the change before it is merged whenever practical.

## Review Expectations

Code review should focus on:

- Whether the change satisfies the intended user story
- Whether the implementation is understandable and maintainable
- Whether existing functionality is affected
- Whether tests are sufficient for the change
- Whether secrets, credentials, or machine-specific configuration were accidentally committed
- Whether the change fits the current architecture

Review comments should identify the problem and, when useful, suggest a possible direction for resolving it.

## Definition of Done

A task or user story is complete when:

- The intended behavior is implemented
- Acceptance criteria are satisfied
- Relevant tests pass
- Existing functionality has not been knowingly broken
- Required setup or configuration is documented
- No secrets or credentials are committed
- The change is integrated with the current application
- The change can be demonstrated during the sprint review
- The partner has had an opportunity to review the work

## Sprint Cycle

The normal sprint cycle is:

1. Sprint Planning
2. Sprint Work
3. Sprint Review
4. Sprint Retrospective
5. Backlog Update

User stories are used to describe functional work. Story points are not required. Progress may be tracked using completed and remaining tasks, along with burn-down or burn-up views when useful.

## Sprint Review

The sprint review focuses on the working product. Completed user stories should be demonstrated and compared against their acceptance criteria.

Incomplete work should return to the backlog or be explicitly carried into the next sprint rather than being treated as complete.

## Sprint Retrospective

The retrospective focuses on how the team worked during the sprint.

Topics may include:

- Development bottlenecks
- Build or test delays
- Integration issues
- Communication problems
- Work that was divided effectively
- Work that should have been divided differently
- Process changes for the next sprint

The retrospective should produce practical adjustments for the following sprint.

## Scope and Integration

A complete vertical slice is generally preferred over several disconnected partial features.

For example, an early sprint may implement a simplified path such as:

```text
Watchlist
   ↓
Single catalyst source
   ↓
Single confirmation rule
   ↓
Confirmed alert
   ↓
Displayed result
```

Additional detectors, rules, notifications, and backtesting can then be added incrementally.

## Secrets and Configuration

Do not commit:

- API keys
- Database passwords
- Authentication secrets
- Broker credentials
- Private tokens
- Local `.env` files

Placeholder configuration belongs in `.env.example`.
