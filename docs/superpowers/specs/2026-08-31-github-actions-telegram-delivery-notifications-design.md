# GitHub Actions Telegram Notifications Design

**Status:** Revised for Issue #77 on 2026-09-01. This revision extends the trusted notification design introduced by #64 without changing GitHub Actions as delivery authority.

## Decision

KAORI sends **GitHub Actions-only** lifecycle notifications to Telegram. The notifier gives operators enough governed delivery context to understand what work is moving, where it is in the lifecycle, whether human testing may proceed, what failed when blocked, and what action is required next.

This work does not integrate with the KAORI application, Notification Deck, Work Inbox, Activity Log, or application notification-channel code.

The existing KAORI Telegram bot is reused inside the private Telegram Supergroup **KAORI Operations** with Topics enabled:

```text
KAORI Operations
├── 🚨 KAORI Alerts     # application/runtime alerts; out of scope
└── 🔄 GitHub Actions   # GitHub Actions delivery notifications
```

GitHub Actions remains the CI/CD source of truth. Telegram is a best-effort operator notification surface only.

## Goals

- Identify the governed Issue/work item and relevant PR when resolvable.
- Signal when trusted staging is ready for human UAT.
- Signal verified main delivery completion.
- Signal actionable Ready PR Full Admission, staging integration, promotion validation, and post-promotion failures.
- State explicitly whether human testing may proceed.
- Preserve exact-SHA evidence and authoritative GitHub Actions links.
- Keep Draft Developer Check PASS/FAIL silent.
- Keep the Telegram bot token out of PR-controlled `quality.yml`.
- Degrade safely when Issue/PR metadata cannot be resolved; never fabricate context.

## Non-Goals

- Any KAORI application integration.
- Changes to `🚨 KAORI Alerts` routing.
- Creating a second bot.
- Mirroring every GitHub Actions job or step.
- Draft Developer Check notifications.
- Release or deployment notifications owned by #47–#51.

## Telegram Destination Contract

All delivery notifications go to topic `🔄 GitHub Actions`.

- `TELEGRAM_CHAT_ID` identifies the `KAORI Operations` Supergroup.
- `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID` is the Telegram `message_thread_id` for `🔄 GitHub Actions`.
- The existing bot receives only the minimum permission required to post messages.

## Repository Configuration Contract

Repository secret:

- `TELEGRAM_BOT_TOKEN` — existing KAORI bot token.

Repository variables:

- `TELEGRAM_CHAT_ID` — numeric Supergroup ID.
- `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID` — numeric Topic `message_thread_id`.
- `TELEGRAM_NOTIFICATIONS_ENABLED` — explicit enable switch; absent/false means safe `SKIP`.

No real token, chat ID, topic ID, or sensitive GitHub token is committed.

## Security Architecture

Privileged PR triggers remain prohibited. KAORI does not expose `TELEGRAM_BOT_TOKEN` to PR-controlled `quality.yml`, and it does not use `workflow_run` or `pull_request_target` to bridge untrusted PR code into the secret-bearing notifier.

The trusted notification authority is `.github/workflows/telegram-github-actions.yml`:

- trusted `push` events on `kaori/staging` and `main` handle staging/main delivery boundaries;
- a trusted scheduled observer scans completed PR-triggered `quality.yml` runs using read-only GitHub metadata permissions;
- `contents`, `actions`, `pull-requests`, and `issues` are read-only;
- Draft Developer Check remains outside Telegram notification routing;
- a successful PR-failure notification emits a receipt artifact keyed by the authoritative quality run ID so the same failure is not repeatedly sent;
- Telegram delivery never changes the authoritative KAORI CI conclusion.

The scheduled observer is intentionally not a PR-triggered secret consumer. It evaluates already-completed GitHub Actions metadata from trusted workflow code.

### Residual Risk

Repository secrets are repository-scoped and are not security-equivalent to Environment secrets. A malicious workflow change merged to a trusted branch could attempt to consume a repository secret. KAORI mitigates this through the governed Draft → Developer Check → Ready → Full Admission → staging/UAT → main process and blocking workflow-security contracts. If the organization plan later supports the preferred private-repository Environment-secret model, the token may move without changing the message contract.

## Notification Categories

All emitted events share the same Telegram topic.

| Category | Events | Meaning |
| --- | --- | --- |
| CI / Quality | `CANDIDATE_BLOCKED`, `STAGING_DELIVERY_FAILED` | a governed candidate or staging delivery path is blocked |
| UAT | `UAT_REQUIRED` | exact staging lineage is machine-verified and ready for human UAT |
| Promotion | `PROMOTION_BLOCKED`, `PRODUCTION_VERIFICATION_FAILED`, `DELIVERY_COMPLETE` | promotion is blocked, production lineage verification failed, or accepted main delivery is complete |

Reserved future categories:

| Category | Future events | Intended use |
| --- | --- | --- |
| Release | `RELEASE_PUBLISHED`, `RELEASE_FAILED` | governed release/tag/image lifecycle |
| Deployment | `DEPLOYMENT_STARTED`, `DEPLOYMENT_SUCCEEDED`, `DEPLOYMENT_FAILED`, `ROLLBACK_REQUIRED` | production deployment lifecycle |

## Event Routing

| Event | Trigger condition | Testability |
| --- | --- | --- |
| `CANDIDATE_BLOCKED` | Ready PR / Full Admission reaches an actionable failed conclusion | Do not test |
| `STAGING_DELIVERY_FAILED` | exact-SHA `kaori/staging` KAORI CI fails actionably | Do not test |
| `PROMOTION_BLOCKED` | staging→main promotion PR validation fails actionably | Do not test |
| `PRODUCTION_VERIFICATION_FAILED` | exact-SHA `main` post-promotion verification fails actionably | Delivery not complete |
| `UAT_REQUIRED` | exact-SHA `kaori/staging` KAORI CI succeeds | Ready for UAT |
| `DELIVERY_COMPLETE` | exact-SHA `main` post-promotion verification succeeds | No additional delivery test required |

Cancelled or superseded runs remain silent. Draft Developer Check remains silent.

## Profile Resolution

- Ready PR → `kaori/staging`: `pr-integration`.
- push → `kaori/staging`: `staging-integration`.
- `kaori/staging` → `main` promotion PR: `promotion`.
- push → `main`: `post-promotion`.

Execution mode is inferred from completed jobs. A successful concise or legacy Fast Smoke job means `fast`; otherwise the selected path is Full for evidence wording.

## Exact-SHA and PR Run Discovery

Trusted branch notifications query `quality.yml` and accept only a completed push run matching both exact source SHA and exact branch.

The scheduled failure observer queries completed PR-triggered `quality.yml` runs and selects only actionable governed profiles. It excludes runs already represented by a `kaori-telegram-quality-run-<run_id>` receipt artifact.

Missing or invalid metadata never produces a fabricated Issue or PR identity.

## Governed Context Resolution

The notifier resolves context from GitHub using read-only calls:

1. identify the relevant PR from the explicit PR number, source commit association, or governed merge lineage;
2. read the PR body and resolve a governed Issue reference such as `Refs #77`, `Closes #77`, `Fixes #77`, or `Resolves #77`;
3. fetch Issue/PR title, state, and authoritative GitHub URL;
4. read the first UAT checklist item as test guidance when available;
5. degrade to the available PR context or `Delivery context unavailable` if resolution is incomplete.

## Message Contract

Messages are plain text and expose operator-facing sections when applicable:

- **Work** — Issue/work identifier and title.
- **Delivery** — stage, status, and environment.
- **Testing** — `Ready for UAT`, `Do not test yet`, or completion guidance.
- **Failure** — first actionable failed gate for blocked deliveries.
- **Evidence** — concise Admission/Fast Smoke evidence and exact short SHA.
- **Next** — one required operator action.
- **Tracking** — Issue, PR, and authoritative GitHub Actions links.

Example UAT message:

```text
🧪 KAORI · Ready for UAT

📌 Work
#77 Improve GitHub Actions Telegram delivery context and failure coverage

📍 Delivery
Stage: Staging Integration
Status: READY FOR UAT
Environment: kaori/staging

🧪 Testing
Ready for UAT
Validate: <governed UAT guidance>

✅ Evidence
Full Admission evidence reused + Fast Integration Smoke PASS
Commit: 1234567890ab

➡️ Next
Complete human UAT before promotion to main.

🔗 Tracking
Issue: #77 · Open
https://github.com/OXY7O/KAORI/issues/77
PR: #79 · Merged
https://github.com/OXY7O/KAORI/pull/79
CI: https://github.com/OXY7O/KAORI/actions/runs/123
```

## Failure Semantics

- `TELEGRAM_NOTIFICATIONS_ENABLED` missing/false: `SKIP`.
- Enabled but token/chat/topic incomplete: `SKIP`.
- No actionable delivery event: `SKIP`.
- Exact-SHA trusted-branch KAORI CI cannot be found/completed inside the bounded wait: notifier fails without changing KAORI CI authority.
- Scheduled PR observer finds no unnotified actionable failure: `SKIP`.
- GitHub metadata lookup fails: notifier fails closed for the attempted notification; no context is invented.
- Telegram API/network rejection: notifier reports failure while original KAORI CI result remains unchanged.

## Governed Rollout for #77

1. Develop on the dedicated #77 issue branch with the PR kept Draft.
2. Keep Draft Developer Check notifications silent while repairing findings.
3. Require the latest Developer Check to pass before freezing the Ready candidate.
4. Run Full Admission on the Ready PR to `kaori/staging`.
5. Verify actionable Ready-PR failure routing contract without exposing the Telegram secret to PR-controlled code.
6. Merge the admitted candidate to `kaori/staging`.
7. Require staging integration/Fast Smoke evidence and verify the real `UAT_REQUIRED` message with Issue/PR context.
8. Complete human UAT before promotion to `main`.
9. Validate the staging→main promotion PR and verify blocked-promotion routing contract.
10. Promote only the accepted staging lineage, then verify `DELIVERY_COMPLETE` on main before closing #77.
