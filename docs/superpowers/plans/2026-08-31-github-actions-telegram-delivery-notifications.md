# GitHub Actions Telegram Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send secure, categorized GitHub Actions lifecycle notifications to the `🔄 GitHub Actions` Telegram topic using the existing KAORI bot.

**Architecture:** A standalone Python standard-library notifier classifies completed `KAORI CI` workflow runs and sends plain-text Telegram messages to a configured Supergroup topic. A separate `workflow_run` subscriber owns notification delivery so Telegram can never become authoritative to `quality.yml` Admission results.

**Tech Stack:** GitHub Actions YAML, Python 3 standard library, pytest release contracts.

**Spec:** `docs/superpowers/specs/2026-08-31-github-actions-telegram-delivery-notifications-design.md`

## Global Constraints

- Scope is GitHub Actions only; no KAORI application integration.
- Telegram parent is `KAORI Operations`; target Topic is `🔄 GitHub Actions`.
- Existing KAORI bot is reused.
- GitHub Environment is exactly `kaori-github-actions`.
- Secret is exactly `TELEGRAM_BOT_TOKEN`.
- Variables are exactly `TELEGRAM_CHAT_ID`, `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID`, and `TELEGRAM_NOTIFICATIONS_ENABLED`.
- No real token/chat/topic value is committed.
- Notifications are categorized as `CI / Quality`, `Security`, `UAT`, or `Promotion`.
- Fork/untrusted workflow runs cannot consume Environment credentials.
- Telegram delivery cannot change authoritative `KAORI CI` conclusions.
- Notification workflow uses `ubuntu-latest`, not the KAORI self-hosted runner.
- Telegram transport uses fixed `https://api.telegram.org` and `message_thread_id`.

---

### Task 1: Lock the revised contract

**Files:**
- Test: `tests/contracts/release/test_ci_telegram_delivery_notification_contract.py`

**Interfaces:**
- Produces the required workflow/environment/topic/category contract.

- [x] **Step 1: Assert standalone notification workflow and trust guard.**
- [x] **Step 2: Assert governed profile/event routing.**
- [x] **Step 3: Assert stable notification categories.**
- [x] **Step 4: Assert topic-aware configuration and transport.**

### Task 2: Implement centralized classification and transport

**Files:**
- Create: `scripts/ci_delivery_notify.py`
- Test: `tests/contracts/release/test_ci_telegram_delivery_notification_contract.py`

**Interfaces:**
- `select_event(*, profile, execution, admission_result, security_result) -> str | None`
- `resolve_profile(*, event_name, head_branch, base_branch) -> str`
- `event_category(event) -> str`
- `configuration_status(*, enabled, bot_token, chat_id, topic_id) -> tuple[bool, str]`
- `render_message(...) -> str`
- `fetch_workflow_jobs(...) -> list[dict]`
- `send_message(..., chat_id, topic_id, ...) -> tuple[bool, str]`

- [x] **Step 1: Implement CI / Quality, Security, UAT, and Promotion event mapping.**
- [x] **Step 2: Infer execution and first failure from completed KAORI CI jobs.**
- [x] **Step 3: Implement fail-safe environment configuration.**
- [x] **Step 4: Implement HTTPS Telegram `sendMessage` with `message_thread_id`.**
- [x] **Step 5: Keep token/chat/topic values out of logs.**

### Task 3: Add isolated `workflow_run` subscriber

**Files:**
- Create: `.github/workflows/telegram-github-actions.yml`

**Interfaces:**
- Subscribes to `KAORI CI` `workflow_run` completion.
- Checks out notifier code from trusted default branch.
- Uses `kaori-github-actions` Environment.
- Uses `actions: read` to inspect completed job conclusions.

- [x] **Step 1: Add `KAORI GitHub Actions Telegram Notification` workflow.**
- [x] **Step 2: Reject workflow runs whose head repository is not the KAORI repository.**
- [x] **Step 3: Run notification on `ubuntu-latest`.**
- [x] **Step 4: Mark only Telegram send step `continue-on-error: true`.**

### Task 4: Align canonical design and governance

**Files:**
- Modify: `docs/superpowers/specs/2026-08-31-github-actions-telegram-delivery-notifications-design.md`
- Modify: this plan.

- [x] **Step 1: Remove all KAORI application/website integration references.**
- [x] **Step 2: Document `KAORI Operations` Topic model and GitHub Environment contract.**
- [x] **Step 3: Document `workflow_run` rollout constraint: live delivery starts after workflow exists on default branch.**

### Task 5: Targeted verification and Draft review

**Files:**
- Test: `tests/contracts/release/test_ci_telegram_delivery_notification_contract.py`
- Test: `tests/contracts/release/test_progressive_ci_admission_contract.py`
- Test: `tests/contracts/release/test_draft_pr_admission_boundary_contract.py`
- Test: `tests/contracts/release/test_kaori_delivery_governance_contract.py`

- [ ] **Step 1: Run Ruff/format checks for changed Python.**
- [ ] **Step 2: Run release contracts covering Telegram and progressive CI.**
- [ ] **Step 3: Open Draft PR to `kaori/staging`.**
- [ ] **Step 4: Review workflow trust boundary, secret exposure, event noise, category routing, and Admission independence.**
- [ ] **Step 5: Repair all Critical/Important findings while Draft.**

### Task 6: Ready Admission and staging UAT

- [ ] **Step 1: Move final candidate to Ready using the established KAORI Draft→Ready process.**
- [ ] **Step 2: Expect one fresh Full Admission because validation-authority files changed.**
- [ ] **Step 3: Merge to `kaori/staging` only after review-clean Full Admission PASS.**
- [ ] **Step 4: Verify Staging Integration evidence reuse + Fast Integration Smoke.**
- [ ] **Step 5: Record explicit human UAT for repository behavior/configuration.**

### Task 7: Telegram configuration and live proof after default-branch promotion

**Files:**
- No credential values are committed.

- [ ] **Step 1: Create/convert `KAORI Operations` to a private Supergroup with Topics enabled.**
- [ ] **Step 2: Create Topics `🚨 KAORI Alerts` and `🔄 GitHub Actions`.**
- [ ] **Step 3: Add the existing KAORI bot with minimum post permission.**
- [ ] **Step 4: Configure Environment `kaori-github-actions`: secret `TELEGRAM_BOT_TOKEN`; variables `TELEGRAM_CHAT_ID`, `TELEGRAM_GITHUB_ACTIONS_TOPIC_ID`, `TELEGRAM_NOTIFICATIONS_ENABLED=true`.**
- [ ] **Step 5: Promote the reviewed implementation to `main`; `workflow_run` subscriber becomes live on the default branch.**
- [ ] **Step 6: Prove one real categorized Telegram notification and confirm it lands in `🔄 GitHub Actions`.**
