# GitHub Actions Telegram Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or subagent-driven-development to implement this plan task-by-task.

**Goal:** Deliver secure, actionable GitHub Actions lifecycle notifications to `KAORI Operations → 🔄 GitHub Actions` under the current GitHub Free/private-repository constraints.

**Architecture:** PR validation stays entirely inside `quality.yml` and never receives Telegram credentials. A separate push-only notifier runs only on trusted `kaori/staging` and `main`, reads repository-scoped Telegram configuration, waits for the authoritative `quality.yml` run for the exact same SHA, then emits `UAT_REQUIRED`, `PROMOTION_SUCCEEDED`, or `DELIVERY_FAILED`.

**Tech Stack:** GitHub Actions YAML, Python 3 standard library, pytest release contracts.

**Spec:** `docs/superpowers/specs/2026-08-31-github-actions-telegram-delivery-notifications-design.md`

## Global Constraints

- GitHub Actions only; no KAORI application integration.
- Telegram parent: `KAORI Operations`; target Topic: `🔄 GitHub Actions`.
- Reuse existing KAORI bot.
- Current platform: GitHub Free organization + private KAORI repository.
- Repository secret: `TELEGRAM_BOT_TOKEN`.
- Repository variables: `TELEGRAM_CHAT_ID`, `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID`, `TELEGRAM_NOTIFICATIONS_ENABLED`.
- No real credential/destination value in Git.
- PR CI must not consume or forward Telegram secrets.
- Telegram failure cannot alter authoritative KAORI CI conclusions.
- Notification workflow uses `ubuntu-latest`.
- `workflow_run`, `pull_request_target`, `workflow_call`, and PR notification callers are prohibited in the active notifier design.
- CI output-style cleanup remains deferred to Issue #68.

---

### Task 1: Preserve completed notifier transport and message contract

- [x] Telegram HTTPS transport with topic-aware `message_thread_id`.
- [x] Safe disabled/incomplete configuration behavior.
- [x] Operator-facing `UAT_REQUIRED`, `PROMOTION_SUCCEEDED`, and failure messages.
- [x] No credential value printed by notifier code.

### Task 2: Record the Environment-secret platform finding

- [x] Full Admission #462 passed for the phase-2 caller candidate.
- [x] PR #71 merged to staging as `cad7c785019afa21c74cd051d859751e82cb72ef`.
- [x] Staging #463 reused exact evidence and passed Fast Smoke + Admission.
- [x] Local Telegram API proof validated bot token, chat, and topic 3688.
- [x] Repeated notifier runs proved Environment vars are injected while `TELEGRAM_BOT_TOKEN` remains empty.
- [x] Confirm OXY7O plan `free` and KAORI visibility `private`.

### Task 3: Lock revised security boundary with failing contracts

**Files:**
- `tests/contracts/release/test_ci_telegram_quality_caller_contract.py`
- `tests/contracts/release/test_ci_telegram_delivery_notification_contract.py`

- [x] Require `quality.yml` to contain no Telegram caller/configuration.
- [x] Require notifier workflow to be push-only for `kaori/staging` and `main`.
- [x] Require no Environment binding in the active notifier workflow.
- [x] Require exact-SHA run discovery and trusted-push-only event selection.
- [x] Require PR and promotion profiles to remain Telegram-silent.

### Task 4: Implement trusted-branch notifier workflow

**File:** `.github/workflows/telegram-github-actions.yml`

- [ ] Replace `workflow_call` with push branches `kaori/staging` and `main`.
- [ ] Remove Environment binding and caller-specific PR guards.
- [ ] Guard exact repository + push + trusted branch refs.
- [ ] Checkout exact push SHA with `persist-credentials: false`.
- [ ] Read repository secret and repository variables directly.
- [ ] Invoke notifier in exact-SHA discovery mode.

### Task 5: Remove Telegram from PR-controlled KAORI CI

**File:** `.github/workflows/quality.yml`

- [ ] Remove `telegram-notification` job completely.
- [ ] Keep all existing Admission authority/profile behavior unchanged.
- [ ] Do not rename jobs or polish CI output in this bundle.

### Task 6: Add exact-SHA KAORI CI discovery and trusted event routing

**File:** `scripts/ci_delivery_notify.py`

- [ ] Add pure matching logic for `push` + exact SHA + exact branch.
- [ ] Add bounded polling of `quality.yml` runs until matching run is terminal.
- [ ] Use the discovered KAORI CI run ID/jobs/conclusion/run URL for classification.
- [ ] Emit only `UAT_REQUIRED`, `PROMOTION_SUCCEEDED`, and trusted-branch `DELIVERY_FAILED`.
- [ ] Keep PR Integration and promotion-PR profiles silent.

### Task 7: Validate the one-bundle candidate

- [ ] Run targeted Telegram/release contract tests.
- [ ] Run formatter/static checks required by the changed Python/YAML/test paths.
- [ ] Open one Ready candidate PR to `kaori/staging` under Issue #64.
- [ ] Run one fresh Full Admission because workflow authority/security boundaries changed.
- [ ] Freeze the candidate head while Full Admission is authoritative.

### Task 8: Migrate live repository configuration and prove delivery

- [ ] Maintainer creates repository secret `TELEGRAM_BOT_TOKEN` (no `--env`).
- [ ] Maintainer creates repository variables with chat ID, topic ID 3688, and enabled=true.
- [ ] Merge exact admitted candidate to `kaori/staging`.
- [ ] Verify staging evidence reuse + Fast Smoke + Admission PASS.
- [ ] Verify notifier discovers the same staging SHA and sends real `UAT_REQUIRED`.
- [ ] Verify no credential value appears in logs/artifacts.
- [ ] Record explicit human UAT acceptance.
- [ ] Promote staging to `main`, verify `PROMOTION_SUCCEEDED`, then close #64 after final Project metadata synchronization.
