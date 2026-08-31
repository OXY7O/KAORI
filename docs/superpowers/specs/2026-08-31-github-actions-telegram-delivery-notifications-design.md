# GitHub Actions Telegram Delivery Notifications Design

**Status:** Approved in chat on 2026-08-31 under Issue #64.

## Decision

KAORI will reuse the existing Telegram bot while routing GitHub Actions delivery lifecycle signals to a dedicated Telegram channel named **KAORI Delivery**. Operational/runtime alerts continue to use the existing operational alert destination.

Telegram is a delivery surface, not delivery authority. GitHub Actions, immutable Admission evidence, exact lineage checks, and explicit human UAT remain authoritative.

## Goals

- Let operators follow delivery state without continuously watching GitHub.
- Notify only actionable lifecycle boundaries, not raw job/step noise.
- Send a clear UAT-required signal after machine-verified staging integration.
- Separate operational alerts from engineering delivery notifications.
- Keep credentials out of repository content, logs, artifacts, outputs, and summaries.
- Preserve all existing Full Admission, evidence reuse, smoke, review, and UAT authority.

## Non-Goals

- Replacing the existing KAORI operational Telegram channel.
- Creating a second bot for the initial rollout.
- Mirroring all GitHub Actions jobs.
- Implementing production deployment itself.
- Implementing GitHub event ingestion into KAORI Notification Deck / Work Inbox in this Issue.

## Destination Model

```text
Existing KAORI Telegram Bot
├── Operational events → existing KAORI Alerts destination
└── Delivery events    → new KAORI Delivery destination
```

The delivery destination is configured independently so bot reuse does not couple alert and delivery routing.

## GitHub Environment Contract

Environment name: `kaori-delivery`

Secret:
- `TELEGRAM_BOT_TOKEN` — existing KAORI bot token.

Variables:
- `TELEGRAM_DELIVERY_CHAT_ID` — private numeric `-100...` chat ID or `@channelusername`.
- `TELEGRAM_DELIVERY_ENABLED` — explicit enable switch; only accepted true values enable delivery.
- `KAORI_UAT_URL` — optional direct KAORI website UAT entry point.

The workflow references the environment declaratively. A missing or disabled configuration produces `SKIP`, not a false CI failure. Telegram transport errors remain visible as notification warnings but do not override authoritative Admission results.

No Environment protection rule should require approval merely to send notifications; such a rule would turn notification delivery into a deployment blocker. Environment access is instead restricted by workflow trust guards and repository governance.

## Trust Boundary

Notification credentials may be consumed only when:
- the KAORI validation profile resolved successfully; and
- for pull requests, the PR head repository equals the KAORI repository; and
- the PR is non-draft because Draft PRs never reach governed Admission.

Fork/untrusted PRs must never gain access to `kaori-delivery` credentials.

The notification job uses a GitHub-hosted runner so Telegram delivery does not consume the constrained KAORI self-hosted validation runner.

## Event Vocabulary

| KAORI event | Trigger | Operator meaning |
| --- | --- | --- |
| `FULL_ADMISSION_PASSED` | final PR Integration succeeds with fresh Full execution | final candidate admitted; staging merge may proceed |
| `SECURITY_GATE_FAILED` | Admission fails and static security gate failed | inspect security evidence before retry |
| `DELIVERY_FAILED` | selected Admission path fails for another reason | repair first failing delivery gate |
| `UAT_REQUIRED` | Staging Integration succeeds | exact staging SHA is ready for human UAT |
| `PROMOTION_VALIDATED` | staging → main promotion validation succeeds | accepted staging lineage is safe to merge to main |
| `PROMOTION_SUCCEEDED` | Post-promotion main verification succeeds | promoted lineage is verified on main |

A successful reused PR Integration retry does not emit `FULL_ADMISSION_PASSED`; this avoids duplicate success noise when the immutable candidate was already admitted.

Future release/deployment events can extend the same vocabulary with `RELEASE_PUBLISHED`, `DEPLOYMENT_STARTED`, `DEPLOYMENT_SUCCEEDED`, `DEPLOYMENT_FAILED`, and `ROLLBACK_REQUIRED` without changing Telegram transport semantics.

## Message Contract

Messages are plain text to avoid markup injection and contain:
- icon + `KAORI · <event title>`;
- event code;
- boundary/environment;
- result;
- short exact source SHA;
- evidence summary when useful;
- one next action;
- PR reference when available;
- GitHub workflow link;
- optional KAORI UAT link for `UAT_REQUIRED`.

Example:

```text
🧪 KAORI · UAT Required

Event: UAT_REQUIRED
Environment: Staging
Result: PASS
Commit: 1234567890ab
Evidence: Full Admission evidence reused + Fast Integration Smoke PASS
Action: Complete UAT before promotion to main.

View Run: https://github.com/OXY7O/KAORI/actions/runs/123
Open KAORI UAT: https://kaori.example/uat
```

## Transport Contract

The CI helper uses Python standard library only and follows the same transport posture as KAORI's existing Telegram notification provider:
- fixed `https://api.telegram.org` authority;
- form-encoded `sendMessage` POST;
- no token/chat value logging;
- no Telegram response body surfaced on HTTP errors;
- bounded timeout;
- link previews disabled;
- generic sanitized failure reporting.

The bot token is passed only through process environment, never a CLI argument.

## Failure Semantics

- Missing `TELEGRAM_DELIVERY_ENABLED=true`: `SKIP`.
- Enabled but missing bot token/chat ID: `SKIP` with configuration-incomplete reason.
- No actionable event for the current profile: `SKIP`.
- Telegram API/network failure: notifier exits non-zero; workflow marks only the notification step as tolerated and emits a GitHub warning.
- Admission failure remains Admission failure regardless of Telegram availability.
- Admission success remains Admission success regardless of Telegram availability.

This keeps communication best-effort while delivery authority remains fail-closed where it matters.

## Website Integration Seam

`UAT_REQUIRED` includes optional `KAORI_UAT_URL`. A later Issue may ingest normalized delivery events into KAORI Notification Deck, Work Inbox, Activity Log, and toast surfaces. That follow-up should reuse the event vocabulary here rather than parse Telegram messages or raw GitHub job names.
