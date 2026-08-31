# GitHub Actions Telegram Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or subagent-driven-development to implement this plan task-by-task.

**Goal:** Send secure, categorized GitHub Actions lifecycle notifications to the `🔄 GitHub Actions` Telegram topic using the existing KAORI bot.

**Architecture:** A Python standard-library notifier classifies KAORI CI results. Notification delivery lives in a reusable `workflow_call` workflow. The reusable workflow is first promoted to trusted `main`; only then does a follow-up `quality.yml` change call that trusted workflow. This avoids `workflow_run` and keeps Telegram non-authoritative to Admission.

**Tech Stack:** GitHub Actions YAML, Python 3 standard library, pytest release contracts.

**Spec:** `docs/superpowers/specs/2026-08-31-github-actions-telegram-delivery-notifications-design.md`

## Global Constraints

- GitHub Actions only; no KAORI application integration.
- Telegram parent: `KAORI Operations`; target Topic: `🔄 GitHub Actions`.
- Reuse existing KAORI bot.
- GitHub Environment: `kaori-github-actions`.
- Secret: `TELEGRAM_BOT_TOKEN`.
- Variables: `TELEGRAM_CHAT_ID`, `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID`, `TELEGRAM_NOTIFICATIONS_ENABLED`.
- No real credential/destination value in Git.
- Categories: `CI / Quality`, `Security`, `UAT`, `Promotion`.
- Reserved future categories: `Release`, `Deployment`.
- Telegram failure cannot alter authoritative KAORI CI conclusions.
- Notification workflow uses `ubuntu-latest`.
- Telegram transport is HTTPS-only and topic-aware.
- `workflow_run` and `pull_request_target` are prohibited for this notifier.

---

### Task 1: Lock notification semantics

- [x] Define CI / Quality, Security, UAT, and Promotion event mapping.
- [x] Define concise operator-facing messages with one next action.
- [x] Define topic-aware configuration and safe disabled state.
- [x] Reserve Release and Deployment categories without emitting them.

### Task 2: Implement classifier and Telegram transport

**Files:**
- `scripts/ci_delivery_notify.py`
- `tests/contracts/release/test_ci_telegram_delivery_notification_contract.py`

- [x] Implement event/profile resolution.
- [x] Inspect KAORI CI jobs through `actions: read`.
- [x] Infer fast/full execution and first actionable failure.
- [x] Send Telegram `sendMessage` with `message_thread_id`.
- [x] Keep bot/chat/topic values out of logs.
- [x] Keep disabled/incomplete configuration as safe `SKIP`.

### Task 3: Bootstrap trusted reusable workflow

**File:** `.github/workflows/telegram-github-actions.yml`

- [x] Replace rejected `workflow_run` trigger with `workflow_call` only.
- [x] Keep permissions at `contents: read` + `actions: read`.
- [x] Reject foreign-repository and Draft PR caller contexts.
- [x] Checkout notifier code from governed default branch, never caller PR source SHA.
- [x] Route caller metadata through environment variables before shell use.
- [x] Reference Environment `kaori-github-actions` inside the called workflow.
- [x] Keep Telegram send step `continue-on-error: true`.

### Task 4: Security finding repair

- [x] Record Full Admission #445 failure: Zizmor `dangerous-triggers` on `workflow_run`.
- [x] Reject suppression as the fix.
- [x] Adopt Zizmor-recommended reusable-workflow architecture.
- [x] Add regression contract: `workflow_run` and `pull_request_target` must not appear.

### Task 5: Bootstrap Draft review and Full Admission

- [x] Reopen Draft review companion #65 after the security redesign.
- [x] Close superseded final candidate #66 unmerged.
- [x] Complete structured review of the reusable trust boundary.
- [x] Repair all Critical/Important findings while Draft.
- [x] Open final bootstrap candidate #67 after review is clean.
- [x] Run fresh Full Admission #455 for final bootstrap head `48be73d9c821616a954dc6d49b63bb44714848ca`.

### Task 6: Bootstrap staging, UAT, and promotion

- [x] Merge bootstrap candidate #67 to `kaori/staging` after Full Admission PASS.
- [x] Verify Staging Integration #456 reuses exact evidence + Fast Integration Smoke PASS.
- [x] Record explicit human UAT acceptance on 2026-08-31.
- [x] Promote accepted staging lineage through PR #69 to `main`.
- [x] Verify promotion #457 and post-promotion #458 reuse exact evidence + Fast Integration Smoke PASS.
- [x] Record trusted `main` SHA `43ca843a09835a53bd72a7513a82f891164736d6` containing the reusable notifier.

### Task 7: Activate notifier from KAORI CI

**File:** `.github/workflows/quality.yml`

This task starts only after Task 6 establishes the reusable workflow on trusted `main`.

- [x] Create follow-up branch `feat-64-telegram-quality-caller` and Draft PR #70 under Issue #64.
- [x] Add a final notification caller job to `quality.yml` pinned to trusted main SHA `43ca843a09835a53bd72a7513a82f891164736d6`.
- [x] Ensure the caller waits for authoritative `admission` completion before classification.
- [x] Use `if: always()` so actionable Admission failures can still be classified.
- [x] Keep the called workflow, Environment secret handling, and Telegram transport outside PR-controlled executable code.
- [ ] Run Draft review → Ready Full Admission → staging reuse/smoke → UAT → promotion.

### Task 8: Enable and prove live Telegram delivery

- [x] Create `KAORI Operations` Telegram Supergroup/Topics.
- [x] Create/configure target Topic `🔄 GitHub Actions`.
- [x] Configure GitHub Environment `kaori-github-actions` with real secret/variables outside Git.
- [x] Keep `TELEGRAM_NOTIFICATIONS_ENABLED=false` through Phase-2 Draft implementation/review.
- [ ] Enable notifications at the controlled staging-test boundary after Phase-2 Ready Full Admission PASS.
- [ ] Prove one real categorized `UAT_REQUIRED` message reaches `🔄 GitHub Actions`.
- [ ] Verify no credential value appears in logs/artifacts.
- [ ] Close #64 only after live delivery and final Project metadata are synchronized.
