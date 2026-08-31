# GitHub Actions Telegram Notifications Design

**Status:** Revised and approved in chat on 2026-08-31 under Issue #64.

## Decision

KAORI will send **GitHub Actions-only** lifecycle notifications directly from GitHub to Telegram. This work does not integrate with the KAORI application, Notification Deck, Work Inbox, Activity Log, or application notification-channel code.

The existing KAORI Telegram bot is reused inside a private Telegram Supergroup named **KAORI Operations** with Topics enabled.

Current topic layout:

```text
KAORI Operations
├── 🚨 KAORI Alerts     # existing application/runtime alerts; out of scope
└── 🔄 GitHub Actions   # GitHub Actions notifications owned by #64
```

GitHub Actions remains the CI/CD source of truth. Telegram is a best-effort operator notification surface only.

## Goals

- Let operators follow KAORI CI/CD state without continuously watching GitHub.
- Send only actionable lifecycle boundaries and failures.
- Signal exactly when staging is ready for human UAT.
- Categorize GitHub Actions notifications without creating unnecessary Telegram topics.
- Keep Telegram credentials and destination IDs out of repository content and logs.
- Keep Telegram transport failure independent from authoritative KAORI CI results.

## Non-Goals

- Any KAORI application integration.
- Changes to `🚨 KAORI Alerts` routing.
- Creating a second bot.
- Mirroring every GitHub Actions job/step.
- Implementing release or production deployment workflows in this Issue.

## Telegram Destination Contract

All #64 notifications go to topic `🔄 GitHub Actions`.

Telegram addressing uses:

- Supergroup `chat_id` → `TELEGRAM_CHAT_ID`.
- Topic `message_thread_id` → `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID`.

The existing bot must be a member/admin of `KAORI Operations` with only the minimum permission needed to post messages.

## GitHub Environment Contract

Environment name: `kaori-github-actions`

Secret:

- `TELEGRAM_BOT_TOKEN` — existing KAORI bot token.

Variables:

- `TELEGRAM_CHAT_ID` — numeric Supergroup ID, normally `-100...`.
- `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID` — numeric Topic `message_thread_id` for `🔄 GitHub Actions`.
- `TELEGRAM_NOTIFICATIONS_ENABLED` — explicit enable switch; absent/false means safe `SKIP`.

No real values are committed to Git.

## Workflow Architecture

Notifications live in a workflow separate from `quality.yml`:

`.github/workflows/telegram-github-actions.yml`

It subscribes to completion of `KAORI CI` through `workflow_run`.

This separation is intentional:

- authoritative Admission jobs do not depend on Telegram;
- Telegram failure cannot turn a valid Admission PASS into CI failure;
- notifier runs on `ubuntu-latest`, not the constrained KAORI self-hosted runner;
- notifier checks out only trusted notifier code from the repository default branch;
- untrusted/fork workflow runs are rejected before environment credentials are exposed.

The notifier reads the completed KAORI CI job conclusions through GitHub Actions API using the workflow token with `actions: read` only.

## Notification Categories

All categories share the same Telegram topic.

| Category | Events | Meaning |
| --- | --- | --- |
| CI / Quality | `FULL_ADMISSION_PASSED`, `DELIVERY_FAILED` | final Admission success or actionable non-security CI failure |
| Security | `SECURITY_GATE_FAILED` | security gate failure requiring review |
| UAT | `UAT_REQUIRED` | exact staging lineage is machine-verified and ready for human UAT |
| Promotion | `PROMOTION_VALIDATED`, `PROMOTION_SUCCEEDED` | staging→main validation or verified main lineage |

Future `Release` and `Deployment` categories may be added by later Issues without changing the Telegram topic or bot.

## Event Routing

| Event | Trigger |
| --- | --- |
| `FULL_ADMISSION_PASSED` | final `PR Integration` succeeds with fresh Full execution |
| `SECURITY_GATE_FAILED` | selected Admission fails and the security job failed |
| `DELIVERY_FAILED` | selected Admission fails for another reason |
| `UAT_REQUIRED` | `Staging Integration` succeeds |
| `PROMOTION_VALIDATED` | staging→main `Promotion` succeeds |
| `PROMOTION_SUCCEEDED` | main `Post-promotion` succeeds |

A successful reused PR Integration retry is intentionally silent to avoid duplicate success noise.

Draft PR runs remain silent because governed Admission is skipped.

## Profile Resolution

The notifier derives the governed boundary from the completed workflow metadata:

- pull request → `kaori/staging`: `pr-integration`;
- push → `kaori/staging`: `staging-integration`;
- pull request `kaori/staging` → `main`: `promotion`;
- push → `main`: `post-promotion`.

Execution mode is inferred from completed jobs. A successful `KAORI Fast Integration Smoke` means `fast`; otherwise the selected path is treated as Full for notification evidence wording.

## Message Contract

Messages are plain text and contain:

- icon + `KAORI · <event title>`;
- category;
- boundary/environment;
- PASS/FAIL result;
- exact short source SHA;
- repository and PR when available;
- evidence summary;
- first failed job when applicable;
- exactly one next action;
- direct GitHub Actions run link.

Example:

```text
🧪 KAORI · UAT Required

Category: UAT
Boundary: Staging Integration
Environment: Staging
Result: PASS
Commit: 1234567890ab
Repository: OXY7O/KAORI
Evidence: Full Admission evidence reused + Fast Integration Smoke PASS
Action: Complete UAT before promotion to main.

View Run: https://github.com/OXY7O/KAORI/actions/runs/123
```

There is no KAORI application URL in this contract.

## Security Contract

- `workflow_run.head_repository.full_name` must equal the KAORI repository before the notification job runs.
- Notifier code is checked out from the trusted default branch, never from the completed untrusted PR SHA.
- Telegram bot token exists only as an Environment secret.
- Bot token/chat/topic IDs are never printed.
- GitHub API and Telegram API authorities are fixed HTTPS endpoints.
- API error responses are sanitized before logging.
- Telegram transport is `continue-on-error` and therefore non-authoritative to Admission.

## Failure Semantics

- `TELEGRAM_NOTIFICATIONS_ENABLED` missing/false: `SKIP`.
- Enabled but token/chat/topic incomplete: `SKIP`.
- Completed Draft/non-actionable workflow: `SKIP`.
- GitHub job inspection failure: notifier reports failure, but notification workflow remains non-authoritative.
- Telegram API/network rejection: notification step reports failure while original `KAORI CI` result remains unchanged.

## Rollout Constraint

A `workflow_run` subscriber becomes live once this workflow exists on the repository default branch. Staging review therefore validates code/contracts/security first; live Telegram delivery is proven after governed promotion to `main` with real Environment values configured by the maintainer.
