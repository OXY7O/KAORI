# GitHub Actions Telegram Notifications Design

**Status:** Revised and approved in chat on 2026-08-31 under Issue #64.

## Decision

KAORI sends **GitHub Actions-only** lifecycle notifications to Telegram. This work does not integrate with the KAORI application, Notification Deck, Work Inbox, Activity Log, or application notification-channel code.

The existing KAORI Telegram bot is reused inside the private Telegram Supergroup **KAORI Operations** with Topics enabled:

```text
KAORI Operations
├── 🚨 KAORI Alerts     # application/runtime alerts; out of scope for #64
└── 🔄 GitHub Actions   # GitHub Actions notifications owned by #64
```

GitHub Actions remains the CI/CD source of truth. Telegram is a best-effort operator notification surface only.

## Goals

- Signal exactly when trusted staging is ready for human UAT.
- Signal verified main promotion completion and trusted-branch delivery failures.
- Keep PR validation inside GitHub Actions only.
- Keep the Telegram bot token out of PR-controlled `quality.yml`.
- Keep Telegram transport independent from authoritative KAORI CI conclusions.
- Work correctly with the current GitHub Free organization and private KAORI repository.

## Non-Goals

- Any KAORI application integration.
- Changes to `🚨 KAORI Alerts` routing.
- Creating a second bot.
- Mirroring every GitHub Actions job or step.
- Sending Telegram notifications for PR Full Admission or promotion-PR validation.
- Release or production deployment workflow implementation in #64.

## Telegram Destination Contract

All #64 notifications go to topic `🔄 GitHub Actions`.

- `TELEGRAM_CHAT_ID` identifies the `KAORI Operations` Supergroup.
- `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID` is the Telegram `message_thread_id` for `🔄 GitHub Actions`.
- The existing bot receives only the minimum permission required to post messages.

## Repository Configuration Contract

The current organization plan is GitHub Free and KAORI is private. Live proof confirmed that Environment variables are available but the Environment secret `TELEGRAM_BOT_TOKEN` is not injected into the private-repository runner. Telegram therefore uses repository-scoped Actions configuration.

Repository secret:

- `TELEGRAM_BOT_TOKEN` — existing KAORI bot token.

Repository variables:

- `TELEGRAM_CHAT_ID` — numeric Supergroup ID.
- `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID` — numeric Topic `message_thread_id`.
- `TELEGRAM_NOTIFICATIONS_ENABLED` — explicit enable switch; absent/false means safe `SKIP`.

No real token, chat ID, or topic ID is committed. The former Environment `kaori-github-actions` is not part of the active notifier contract after migration.

## Security Architecture

The original `workflow_run` subscriber design was rejected by KAORI Security Admission. Zizmor classifies `workflow_run` as a dangerous privileged trigger. KAORI does **not** suppress that finding.

The later reusable `workflow_call` design protected the notifier implementation but depended on an Environment secret. That design cannot deliver the bot token on the current GitHub Free/private-repository combination.

The active design is therefore **trusted-branch push delivery**:

```text
PR / Ready
├── Full Admission PASS/FAIL
└── GitHub Actions UI only

kaori/staging push
├── wait for exact-SHA KAORI CI
├── PASS → UAT_REQUIRED
└── FAIL → DELIVERY_FAILED

main push
├── wait for exact-SHA KAORI CI
├── PASS → PROMOTION_SUCCEEDED
└── FAIL → DELIVERY_FAILED
```

`.github/workflows/telegram-github-actions.yml`:

- triggers only on `push` to `kaori/staging` and `main`;
- has no `pull_request`, `pull_request_target`, `workflow_run`, `workflow_call`, or `workflow_dispatch` trigger;
- uses only `contents: read` and `actions: read`;
- runs on `ubuntu-latest`;
- checks out the exact trusted push SHA with credentials disabled;
- reads `TELEGRAM_BOT_TOKEN` only from repository secrets;
- reads destination/enable values from repository variables;
- discovers the authoritative `quality.yml` run for the exact same SHA and branch;
- waits for that KAORI CI run to become terminal before classification;
- never sends based on the notifier workflow's own conclusion.

`.github/workflows/quality.yml` contains no Telegram caller, token, destination, or notifier reference. PR-controlled CI therefore has no direct path to the Telegram secret.

### Residual Risk

Repository secrets are repository-scoped and are not security-equivalent to Environment secrets. A malicious workflow change merged to a trusted branch could attempt to consume a repository secret. KAORI mitigates this under the current plan through the governed Draft → Ready → Full Admission → staging/UAT → main process and explicit workflow-security contracts. If OXY7O upgrades to a plan supporting Environment secrets for private repositories, the token should move back to an Environment secret without changing the Telegram message contract.

## Notification Categories

All emitted events share the same Telegram topic.

| Category | Events | Meaning |
| --- | --- | --- |
| CI / Quality | `DELIVERY_FAILED` | trusted staging/main delivery path failed |
| UAT | `UAT_REQUIRED` | exact staging lineage is machine-verified and ready for human UAT |
| Promotion | `PROMOTION_SUCCEEDED` | verified main lineage completed successfully |

PR Full Admission and staging→main promotion validation remain visible in GitHub Actions only.

Reserved future categories:

| Category | Future events | Intended use |
| --- | --- | --- |
| Release | `RELEASE_PUBLISHED`, `RELEASE_FAILED` | governed release/tag/image lifecycle |
| Deployment | `DEPLOYMENT_STARTED`, `DEPLOYMENT_SUCCEEDED`, `DEPLOYMENT_FAILED`, `ROLLBACK_REQUIRED` | production deployment lifecycle |

## Event Routing

| Event | Trigger condition |
| --- | --- |
| `UAT_REQUIRED` | exact-SHA `kaori/staging` KAORI CI succeeds |
| `PROMOTION_SUCCEEDED` | exact-SHA `main` KAORI CI succeeds |
| `DELIVERY_FAILED` | exact-SHA staging/main KAORI CI reaches an actionable failed conclusion |

Draft PRs, Ready PRs, Full Admission PR successes/failures, and promotion PR validation are silent in Telegram.

## Profile Resolution

Only trusted push profiles emit Telegram events:

- push → `kaori/staging`: `staging-integration`;
- push → `main`: `post-promotion`.

Execution mode is inferred from completed jobs. A successful `KAORI Fast Integration Smoke` means `fast`; otherwise the selected path is Full for evidence wording.

## Exact-SHA Run Discovery

The notifier starts independently from KAORI CI on the same trusted branch push. It queries the GitHub Actions API for `quality.yml` runs and accepts only a run matching all of:

- event `push`;
- exact `head_sha` equal to the notifier source SHA;
- exact `head_branch` equal to `kaori/staging` or `main`.

The notifier waits with a bounded retry window until the matching run reaches `completed`. A missing or non-terminal run never produces a Telegram success notification.

## Message Contract

Messages are plain text and contain:

- icon + `KAORI · <event title>`;
- category;
- boundary/environment;
- PASS/FAIL result;
- short source SHA;
- repository;
- evidence summary;
- first failed job when applicable;
- exactly one next action;
- direct authoritative GitHub Actions run link.

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

## Failure Semantics

- `TELEGRAM_NOTIFICATIONS_ENABLED` missing/false: `SKIP`.
- Enabled but repository token/chat/topic incomplete: `SKIP`.
- PR or other non-trusted lifecycle boundary: no notifier workflow run.
- Exact-SHA KAORI CI cannot be found/completed inside the bounded wait: notifier fails without changing KAORI CI authority.
- Telegram API/network rejection: notifier reports failure while original KAORI CI result remains unchanged.

## Rollout

1. Admit the redesign as one Issue #64 bundle.
2. Configure repository secret/variables outside Git.
3. Merge the admitted bundle to `kaori/staging`.
4. Verify exact Full Admission evidence reuse + Fast Smoke.
5. Verify a real `UAT_REQUIRED` message in `KAORI Operations → 🔄 GitHub Actions`.
6. Human UAT, then promote the accepted staging lineage to `main`.
7. Verify `PROMOTION_SUCCEEDED`, then close #64 after metadata synchronization.
