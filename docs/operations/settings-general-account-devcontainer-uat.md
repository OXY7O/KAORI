# KAORI Settings — General & Account Dev Container UAT

**Authority:** Settings Final Lock, #2225, #2475 and focused QA #2880.
**Operator decision:** General and Account functionality was approved on
2026-10-23. This checklist reviews *additional quality/negative evidence*,
not a request to repeat or redesign the accepted presentation.

**Worktree:** `kaori/review/staging-uat` (UAT holding only).
**Exact local SHA / tested browser versions:** PENDING.
**Official Developer Check / Full Admission / staging / release:** HOLD.

## Local verification

Run against your normal prepared KAORI Dev Container. These are executable
commands for the operator; they have **not** been run by the GitHub-source
authoring session:

```bash
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
git rev-parse HEAD
git status --short

python scripts/verify_settings_final_lock.py
python scripts/verify_notification_surface_style.py
python -m pytest -q \
  tests/contracts/settings/test_settings_uat_negative_boundaries.py \
  tests/contracts/settings/test_compatibility_registry_projection.py \
  tests/contracts/settings/test_account_credential_security_contract.py \
  tests/contracts/settings/test_settings_final_lock_contract.py \
  tests/ui/test_visual_audit_contract.py
```

The **Account-only deterministic browser Visual QA** uses the existing
Playwright fixtures, local mocked login and six canonical viewports. After
installing the repository's existing Playwright/browser prerequisites:

```bash
python -m pytest -q -s \
  tests/ui/test_representative_interactions.py \
  -k settings_account_profile_activity_credentials_visual_qa
```

The test performs *read-only* Profile, Activity and Credentials navigation,
takes screenshots and browser traces in
`tmp/ci-artifacts/test-output/ui-browser/`, and asserts Account responsive
geometry and HTMX tab navigation in light/dark. It never submits passwords.
No Account screenshot hashes are manufactured or locked before review.

## Human UAT evidence matrix

| ID | Scenario | Expected evidence | Current status |
| --- | --- | --- | --- |
| SET-GEN-01 | Time Zone manual/automatic, Detect Again, invalid IANA | No implicit save, CSRF-safe background sync, correct display-only scope | Functional UAT approved; negative browser evidence pending |
| SET-GEN-02 | Regional Format locale/date/time selection | UI-only formatting; stored UTC and schedule authority unchanged | Functional UAT approved; runtime capture pending |
| SET-GEN-03 | System Information with and without `system.view` | No privileged tab/data disclosure; build metadata `Not supplied` truthful; no secret config echo | Source negative regression added; runtime pending |
| SET-GEN-04 | Compatibility filter/reset/search, empty state, pagination 5, selected detail and no-JS | Filter/URL/result/focus correct, source-qualified version never equals live readiness | Pure projection negative regression added; browser pending |
| SET-ACC-01 | Profile local/external identity, RBAC role vs Super Admin | Read-only and source-backed identity; no false live provider readiness | Functional UAT approved; provider-negative evidence pending |
| SET-ACC-02 | Empty/five recent auth events and Activity Audit authorization | Five-event sample, safe status, IP proxy caveat, permitted drill-down | Deterministic empty-state browser coverage added; nonempty/RBAC pending |
| SET-ACC-03 | Credentials Local Database vs external provider | Password field only for local; external owner rejects change | Isolated negative service regression added; runtime pending |
| SET-ACC-04 | Incorrect current password, reuse, CSRF, session generation | No secret leakage; rejected no commit; on legitimate success current session remains, others revoked | Isolated rejection regressions added; cross-session integration pending |
| SET-VIS-01 | Account Profile/Activity/Credentials: six viewports, both themes, keyboard | No horizontal page overflow; shared tab focus/URL; no visual loading bars | New Playwright suite; NOT RUN here |
| SET-OPS-01 | General/Account reload/back navigation, slow HTMX GET, accessibility | Nonvisual `sr-only role=status`, persistent controls/toast, no spinner/bar geometry | Browser/AT evidence pending |

Mark individual cases PASS/FAIL/BLOCKED only after actual execution and link
redacted screenshots/traces/logs with tested SHA, environment, date, reviewer,
expected/actual and follow-up issue. Tests run under fake identities must not
be presented as production-provider or end-to-end session evidence. Avoid
posting passwords or session cookies in GitHub evidence.

**No behavioral UI changes:** shared Violet Hero/cards/HTMX, default five-row
registry pagination and the previously approved no-visible-loading-bar design
remain authoritative. Exact-head Full Admission is a separate future
human-authorized step.
