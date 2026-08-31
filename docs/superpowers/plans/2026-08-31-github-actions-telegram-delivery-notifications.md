# GitHub Actions Telegram Delivery Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add secure, actionable Telegram delivery notifications to KAORI GitHub Actions using the existing bot and a dedicated `KAORI Delivery` destination.

**Architecture:** A small Python standard-library notifier owns event selection, rendering, and Telegram transport. `quality.yml` invokes it from one post-Admission GitHub-hosted job bound to the `kaori-delivery` Environment, with explicit same-repository trust guards and best-effort transport semantics. Existing KAORI Admission, evidence reuse, smoke, and UAT authority are unchanged.

**Tech Stack:** GitHub Actions YAML, Python 3 standard library, pytest contract tests, existing KAORI progressive CI workflow.

**Spec:** `docs/superpowers/specs/2026-08-31-github-actions-telegram-delivery-notifications-design.md`

## Global Constraints

- Reuse the existing KAORI Telegram bot; use a separate `KAORI Delivery` destination.
- GitHub Environment name is exactly `kaori-delivery`.
- Secret name is exactly `TELEGRAM_BOT_TOKEN`.
- Variables are `TELEGRAM_DELIVERY_CHAT_ID`, `TELEGRAM_DELIVERY_ENABLED`, and optional `KAORI_UAT_URL`.
- No real credential or destination value is committed.
- Fork/untrusted PRs cannot consume Environment credentials.
- Telegram delivery cannot weaken, replace, or falsely override authoritative Admission results.
- Draft PRs do not run governed Admission or delivery notification jobs.
- Notification transport uses only `https://api.telegram.org` and Python standard library.
- Do not add a dependency or consume the KAORI self-hosted runner solely for Telegram delivery.

---

### Task 1: Lock the notification contract

**Files:**
- Create: `tests/contracts/release/test_ci_telegram_delivery_notification_contract.py`

**Interfaces:**
- Consumes: `.github/workflows/quality.yml` and future `scripts/ci_delivery_notify.py`.
- Produces: required workflow tokens and notifier API signatures `select_event`, `render_message`, and `configuration_status`.

- [x] **Step 1: Write the failing contract test**

The contract asserts the dedicated Environment, trusted same-repository guard, Environment secret/variables, non-blocking notification step, profile-aware event selection, exact UAT message contents, fail-safe configuration, HTTPS-only transport, and no explicit token/chat logging.

- [ ] **Step 2: Verify RED on the work branch**

Run:

```bash
pytest -q tests/contracts/release/test_ci_telegram_delivery_notification_contract.py
```

Expected before implementation: FAIL because `scripts/ci_delivery_notify.py` and the workflow notification job do not exist.

- [x] **Step 3: Commit the contract**

Commit:

```text
test(ci): lock Telegram delivery notification contract #64
```

### Task 2: Implement centralized event selection and Telegram transport

**Files:**
- Create: `scripts/ci_delivery_notify.py`
- Test: `tests/contracts/release/test_ci_telegram_delivery_notification_contract.py`

**Interfaces:**
- Produces `select_event(*, profile, execution, admission_result, security_result) -> str | None`.
- Produces `render_message(*, event, profile, execution, source_sha, repository, run_url, pr_number, uat_url) -> str`.
- Produces `configuration_status(*, enabled, bot_token, chat_id) -> tuple[bool, str]`.
- CLI consumes GitHub workflow context via arguments and bot/destination values via environment only.

- [ ] **Step 1: Implement event selection**

Map successful `pr-integration/full` to `FULL_ADMISSION_PASSED`, successful `staging-integration` to `UAT_REQUIRED`, successful `promotion` to `PROMOTION_VALIDATED`, and successful `post-promotion` to `PROMOTION_SUCCEEDED`. Failed Admission maps to `SECURITY_GATE_FAILED` when the security gate failed, otherwise `DELIVERY_FAILED`.

- [ ] **Step 2: Implement stable plain-text templates**

Every message includes event, boundary, result, short source SHA, next action, and workflow link. UAT messages include evidence text and optional KAORI UAT URL.

- [ ] **Step 3: Implement fail-safe configuration**

Only explicit values `1`, `true`, `yes`, or `on` enable Telegram delivery. Missing enablement or incomplete credentials returns a `SKIP` reason without showing secret values.

- [ ] **Step 4: Implement Telegram sendMessage transport**

Use fixed `https://api.telegram.org`, `urllib.parse.urlencode`, `urllib.request.Request`, bounded timeout, disabled link preview, and sanitized HTTP/network failure reporting. Never print bot token or destination values.

- [ ] **Step 5: Run targeted contracts**

```bash
pytest -q tests/contracts/release/test_ci_telegram_delivery_notification_contract.py
```

Expected: notifier-specific tests pass; workflow contract remains RED until Task 3.

### Task 3: Add the post-Admission GitHub Actions notification job

**Files:**
- Modify: `.github/workflows/quality.yml`
- Test: `tests/contracts/release/test_ci_telegram_delivery_notification_contract.py`
- Test: `tests/contracts/release/test_progressive_ci_admission_contract.py`
- Test: `tests/contracts/release/test_draft_pr_admission_boundary_contract.py`

**Interfaces:**
- Consumes `needs.validation-profile.outputs.profile`, `execution`, `source_sha`, `needs.admission.result`, and `needs.static-security.result`.
- Consumes Environment secret/variables without placing their values in command arguments.
- Invokes `python scripts/ci_delivery_notify.py` once per actionable completed Admission boundary.

- [ ] **Step 1: Add `KAORI Delivery Notification` job**

Use `runs-on: ubuntu-latest`, `environment.name: kaori-delivery`, read-only contents permission, `if: always()` plus successful validation-profile and same-repository PR trust guard, and `needs` on validation-profile, static-security, and admission.

- [ ] **Step 2: Bind Environment configuration only at the notification step**

```yaml
env:
  TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
  TELEGRAM_DELIVERY_CHAT_ID: ${{ vars.TELEGRAM_DELIVERY_CHAT_ID }}
  TELEGRAM_DELIVERY_ENABLED: ${{ vars.TELEGRAM_DELIVERY_ENABLED }}
  KAORI_UAT_URL: ${{ vars.KAORI_UAT_URL }}
```

- [ ] **Step 3: Keep Telegram transport non-authoritative**

Mark only the notify step `continue-on-error: true`; if it fails, emit `::warning::KAORI Delivery Telegram notification failed; authoritative CI result is unchanged.`

- [ ] **Step 4: Re-run release contracts**

```bash
pytest -q \
  tests/contracts/release/test_ci_telegram_delivery_notification_contract.py \
  tests/contracts/release/test_progressive_ci_admission_contract.py \
  tests/contracts/release/test_draft_pr_admission_boundary_contract.py \
  tests/contracts/release/test_kaori_delivery_governance_contract.py
```

Expected: PASS.

### Task 4: Document operator configuration and preserve governance

**Files:**
- Modify: `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`
- Create: `docs/superpowers/specs/2026-08-31-github-actions-telegram-delivery-notifications-design.md`
- Modify: this plan as progress is completed.

**Interfaces:**
- Produces the canonical `kaori-delivery` Environment and event-routing contract for operators/reviewers.

- [ ] **Step 1: Document notification boundary**

Record that Telegram is best-effort communication while GitHub Admission/evidence/UAT remain authoritative, and document the Environment configuration names without real values.

- [ ] **Step 2: Run formatting and targeted static checks through existing KAORI tooling**

Use existing formatter/lint/test gates only; do not create helper scripts.

### Task 5: Governed Draft review and Ready Admission

**Files:**
- No new source files unless review finds a defect.

**Interfaces:**
- Produces a Draft PR to `kaori/staging`, structured review evidence, then a final Ready candidate Full Admission.

- [ ] **Step 1: Open Draft PR linked to #64**

Draft activity must not consume governed Admission.

- [ ] **Step 2: Review secret exposure, fork trust boundary, event noise policy, and Admission independence**

No Critical/Important finding may remain before Ready.

- [ ] **Step 3: Move final candidate to Ready**

Expect validation-authority fingerprint change from workflow/contracts, therefore one fresh Full Admission for the final candidate.

- [ ] **Step 4: Merge to `kaori/staging` only after Full Admission PASS**

Then verify Staging Integration reuses exact evidence and runs Fast Integration Smoke.

### Task 6: Configure and UAT the real Telegram destination

**Files:**
- No repository secret values are committed.

**Interfaces:**
- Consumes the automatically/declaratively referenced GitHub Environment `kaori-delivery`.

- [ ] **Step 1: Create/add the existing bot to the new `KAORI Delivery` Telegram channel**

Grant only permission needed to post messages.

- [ ] **Step 2: Configure GitHub Environment values**

Set secret `TELEGRAM_BOT_TOKEN`; set `TELEGRAM_DELIVERY_CHAT_ID`; optionally set `KAORI_UAT_URL`; set `TELEGRAM_DELIVERY_ENABLED=true` only after destination verification.

- [ ] **Step 3: Verify one real delivery notification during staging/UAT**

Confirm exact SHA, correct channel, expected action/link, and absence of operational-alert noise.

- [ ] **Step 4: Record explicit human UAT**

UAT remains a user statement and is never inferred from Telegram delivery.
