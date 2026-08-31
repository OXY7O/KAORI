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

- Let operators follow KAORI CI/CD state without continuously watching GitHub.
- Send only actionable lifecycle boundaries and failures.
- Signal exactly when staging is ready for human UAT.
- Categorize notifications without creating unnecessary Telegram topics.
- Keep Telegram credentials and destination IDs out of repository content and logs.
- Keep Telegram transport independent from authoritative KAORI CI conclusions.

## Non-Goals

- Any KAORI application integration.
- Changes to `🚨 KAORI Alerts` routing.
- Creating a second bot.
- Mirroring every GitHub Actions job or step.
- Release or production deployment workflow implementation in #64.

## Telegram Destination Contract

All #64 notifications go to topic `🔄 GitHub Actions`.

- `TELEGRAM_CHAT_ID` identifies the `KAORI Operations` Supergroup.
- `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID` is the Telegram `message_thread_id` for `🔄 GitHub Actions`.
- The existing bot receives only the minimum permission required to post messages.

## GitHub Environment Contract

Environment: `kaori-github-actions`

Secret:

- `TELEGRAM_BOT_TOKEN` — existing KAORI bot token.

Variables:

- `TELEGRAM_CHAT_ID` — numeric Supergroup ID.
- `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID` — numeric Topic `message_thread_id`.
- `TELEGRAM_NOTIFICATIONS_ENABLED` — explicit enable switch; absent/false means safe `SKIP`.

No real token, chat ID, or topic ID is committed.

## Security Architecture

The original `workflow_run` subscriber design was rejected by KAORI Security Admission. Zizmor classifies `workflow_run` as a dangerous privileged trigger. KAORI does **not** suppress that finding.

The notifier is therefore implemented as a reusable workflow:

`.github/workflows/telegram-github-actions.yml`

with only:

```text
on: workflow_call
```

The reusable workflow:

- has no autonomous privileged trigger;
- uses `contents: read` and `actions: read` only;
- rejects foreign-repository and Draft PR caller contexts;
- references GitHub Environment `kaori-github-actions` only inside the trusted notification job;
- checks out notifier code from the governed default branch, never from the PR source SHA;
- passes GitHub event metadata through environment variables before shell use;
- runs on `ubuntu-latest`, not the KAORI self-hosted runner;
- marks Telegram transport `continue-on-error`, so Telegram cannot change Admission authority.

## Two-Phase Trust Bootstrap

### Phase 1 — Bootstrap trusted notifier

The reusable workflow, notifier helper, tests, and documentation are admitted through the normal Draft → Ready → Full Admission → staging → UAT → main lifecycle.

During this phase `quality.yml` does **not** call the notifier. Therefore Environment credentials cannot be consumed by branch-controlled notifier code and no Telegram message is emitted by the bootstrap PR itself.

After promotion, the reusable workflow exists on trusted `main` and becomes an eligible trust anchor.

### Phase 2 — Activate from KAORI CI

A follow-up PR under Issue #64 updates `quality.yml` to call the already-trusted reusable workflow from `main`, preferably using the exact bootstrap promotion SHA.

The caller waits for the governed CI jobs required to classify the lifecycle boundary and invokes the reusable notifier with `if: always()` semantics where failure notification is required. The called workflow receives the caller's GitHub context, inspects the current KAORI CI run using `actions: read`, derives the event category, and sends only an actionable notification.

The caller PR cannot replace the trusted reusable workflow implementation because the call is pinned outside the PR source tree.

## Notification Categories

All categories share the same Telegram topic.

| Category | Events | Meaning |
| --- | --- | --- |
| CI / Quality | `FULL_ADMISSION_PASSED`, `DELIVERY_FAILED` | final Admission success or actionable non-security CI failure |
| Security | `SECURITY_GATE_FAILED` | security gate failure requiring review |
| UAT | `UAT_REQUIRED` | exact staging lineage is machine-verified and ready for human UAT |
| Promotion | `PROMOTION_VALIDATED`, `PROMOTION_SUCCEEDED` | staging→main validation or verified main lineage |

Reserved future categories:

| Category | Future events | Intended use |
| --- | --- | --- |
| Release | `RELEASE_PUBLISHED`, `RELEASE_FAILED` | governed release/tag/image lifecycle |
| Deployment | `DEPLOYMENT_STARTED`, `DEPLOYMENT_SUCCEEDED`, `DEPLOYMENT_FAILED`, `ROLLBACK_REQUIRED` | production deployment lifecycle |

These future categories remain in `🔄 GitHub Actions` unless later notification volume justifies another Telegram Topic.

## Event Routing

| Event | Trigger condition |
| --- | --- |
| `FULL_ADMISSION_PASSED` | final PR Integration succeeds with fresh Full execution |
| `SECURITY_GATE_FAILED` | selected Admission fails and Security gate failed |
| `DELIVERY_FAILED` | selected Admission fails for another reason |
| `UAT_REQUIRED` | Staging Integration succeeds |
| `PROMOTION_VALIDATED` | staging→main Promotion succeeds |
| `PROMOTION_SUCCEEDED` | main Post-promotion succeeds |

A successful reused PR Integration retry remains silent to avoid duplicate success noise. Draft PRs remain silent.

## Profile Resolution

The notifier derives the boundary from caller GitHub metadata:

- pull request → `kaori/staging`: `pr-integration`;
- push → `kaori/staging`: `staging-integration`;
- pull request `kaori/staging` → `main`: `promotion`;
- push → `main`: `post-promotion`.

Execution mode is inferred from completed jobs. A successful `KAORI Fast Integration Smoke` means `fast`; otherwise the selected path is Full for evidence wording.

## Message Contract

Messages are plain text and contain:

- icon + `KAORI · <event title>`;
- category;
- boundary/environment;
- PASS/FAIL result;
- short source SHA;
- repository and PR where applicable;
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

## Failure Semantics

- `TELEGRAM_NOTIFICATIONS_ENABLED` missing/false: `SKIP`.
- Enabled but token/chat/topic incomplete: `SKIP`.
- Draft/non-actionable lifecycle boundary: `SKIP`.
- GitHub job inspection failure: notifier reports failure but original KAORI CI remains authoritative.
- Telegram API/network rejection: notifier reports failure while original KAORI CI result remains unchanged.

## Rollout State

The maintainer has configured GitHub Environment `kaori-github-actions`. Real values remain outside Git. Delivery must remain disabled until the trusted reusable workflow has been promoted and the phase-2 caller has passed its governed lifecycle.
