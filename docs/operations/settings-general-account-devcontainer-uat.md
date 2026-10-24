# KAORI Settings — General & Account Dev Container UAT

**Authority:** Settings Final Lock, #2225, #2475 and focused QA #2880.
**Operator decision:** General and Account functionality was approved on
2026-10-23. This checklist reviews *additional quality/negative evidence*,
not a request to repeat or redesign the accepted presentation.

**Worktree:** `kaori/review/staging-uat` (UAT holding only).
**Evidence SHAs:** Account focused contracts `e026a44ba0c3a16578c4923327dbddfecb8ddd18`; accepted Account Activity table `295e4c84baf018d7df6630766e200cede2f7bd5f`. The standalone six-viewport browser log and final operational screenshot batch did not include an exact same-run SHA. Browser screenshots include Firefox/DevTools; exact automated browser version not captured.
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
| SET-GEN-01 | Time Zone manual/automatic, Detect Again, invalid IANA | No implicit save, CSRF-safe background sync, correct display-only scope | **Human PASS for positive flow (2026-10-24):** manual save/reload, automatic mode, Detect Again, Account effective timezone; invalid-IANA/CSRF negative browser evidence pending |
| SET-GEN-02 | Regional Format locale/date/time selection | UI-only formatting; stored UTC and schedule authority unchanged | Functional UAT approved; runtime capture pending |
| SET-GEN-03 | System Information with and without `system.view` | No privileged tab/data disclosure; build metadata `Not supplied` truthful; no secret config echo | Source negative regression added; runtime pending |
| SET-GEN-04 | Compatibility filter/reset/search, empty state, pagination 5, selected detail and no-JS | Filter/URL/result/focus correct, source-qualified version never equals live readiness | Pure projection negative regression added; browser pending |
| SET-ACC-01 | Profile local/external identity, RBAC role vs Super Admin | Read-only and source-backed identity; no false live provider readiness | **Human PASS (Account scope):** Local Super Admin and LDAP Viewer linked identity/profile screenshots; provider live-readiness was not asserted |
| SET-ACC-02 | Empty/five recent auth events and Activity Audit authorization | Five-event sample, safe status, IP proxy caveat, permitted drill-down | **Human PASS (UI/RBAC boundary):** local + LDAP event sample, Viewer denied at direct audit URL, authorized audit access; separate HTTP 403 header capture not provided |
| SET-ACC-03 | Credentials Local Database vs external provider | Password field only for local; external owner rejects change | **Human PASS (UI boundary):** local password form; LDAP provider-managed recovery without local form; automatic negative contracts also passed in focused suite |
| SET-ACC-04 | Incorrect current password, reuse, CSRF, session generation | No secret leakage; rejected no commit; on legitimate success current session remains, others revoked | **Human PASS (credential & session behavior):** both invalid password UI rejections, dedicated local UAT user successful rotation, old session revoked and current session retained, audit/toast; second rejection audit-detail evidence and independent CSRF browser capture remain pending |
| SET-VIS-01 | Account Profile/Activity/Credentials: six viewports, both themes, keyboard | No horizontal page overflow; shared tab focus/URL; no visual loading bars | **Operator automated PASS:** Playwright 6 passed, 66 deselected, 71.10 s after Chromium dependencies installed; exact browser-run SHA not independently captured |
| SET-OPS-01 | General/Account reload/back navigation, slow HTMX GET, accessibility | Nonvisual `sr-only role=status`, persistent controls/toast, no spinner/bar geometry | **Human PASS for Account only:** navigation/history, HTMX XHR 200, keyboard/focus, light/dark, offline recovery; General/AT-specific coverage not claimed |

## Settings → Account — Gherkin acceptance specification

These six scenario families make the **existing Human UAT decisions** reviewable in
`Given–When–Then` form. They document acceptance behavior and are **not**
executable `.feature` files, new step definitions, or a replacement for KAORI's
existing pytest test taxonomy. The results in the UAT matrix and evidence register
below remain the authority for what was actually observed; a `Then` clause is
an expected contract, **not** proof that a separate trace was captured.

### SET-ACC-01 — Account identity, access posture and provider ownership

```gherkin
Feature: Account identity and access posture
  Scenario Outline: Show canonical identity without treating provider linkage as live health
    Given an active KAORI user authenticated through "<identity_source>"
    And the user has RBAC role "<role>" and administrative tier "<tier>"
    When the user opens Settings > Account > Account Profile & Access
    Then the account identity and authentication source are shown read-only
    And the assigned RBAC role is separate from administrative tier
    And the credential owner is "<credential_owner>"
    And the latest verified sign-in shows locally recorded evidence when available
    And the page does not claim a live identity-provider readiness check

    Examples:
      | identity_source       | role   | tier             | credential_owner       |
      | Local Database        | Admin  | Super Admin      | KAORI                  |
      | LDAP / Active Directory | Viewer | Standard Account | KAORI Active Directory |
```

**Evidence:** Human PASS, local Super Admin and LDAP Viewer screenshots.
Provider health/live readiness was intentionally **not** tested.

### SET-ACC-02 — Recent authentication evidence and audit permission boundary

```gherkin
Feature: Personal authentication activity
  Scenario: Display only the account's latest five authentication events
    Given a signed-in KAORI user has recorded authentication events
    When the user opens Settings > Account > Recent Authentication Activity
    Then no more than five latest events are shown in newest-first order
    And summary counts describe only those displayed events, not full history
    And each event preserves its authentication source and safe result label
    And the recorded IP is presented as request evidence that may be a proxy hop
    And secrets and credential values are absent from the event presentation

  Scenario: Restrict administrative Activity Audit to users with permission
    Given an LDAP Viewer lacks the "activity_audit.view" permission
    And a separate authorized user has "activity_audit.view"
    When the Viewer opens personal Recent Authentication Activity
    Then the "Open Activity Audit" action is not shown
    When the Viewer navigates directly to /access/activity-audit/
    Then the server denies the privileged request without disclosing audit records
    And the KAORI Access Denied guidance is presented
    When a user with "activity_audit.view" opens Activity Audit
    Then that user can review the authorized Activity Register
```

**Evidence:** Human PASS for latest-five samples, denied Viewer UI, and authorized
audit access; deterministic Playwright verifies the empty-activity presentation.
The unauthorized response's **HTTP 403 header was not separately captured**
in the supplied browser evidence; it remains an independent trace limitation.

### SET-ACC-03 — Local versus provider-managed credentials

```gherkin
Feature: Credential ownership boundary
  Scenario: KAORI owns local credentials
    Given a user has a Local Database identity
    When the user opens Settings > Account > Credential Management
    Then KAORI presents the local password-change form
    And the local password policy and session-handling guidance are shown

  Scenario: External providers remain responsible for their credentials
    Given a user is linked to LDAP / Active Directory
    When the user opens Settings > Account > Credential Management
    Then no KAORI local password-change form is available
    And the credential owner and recovery path identify the external provider
    And KAORI retains independent account lifecycle and RBAC enforcement
    And KAORI does not claim to reset or observe the provider's password
```

**Evidence:** Human PASS for local and LDAP credential UIs; isolated automated
negative tests reject external password mutation without committing credentials
or calling the external provider.

### SET-ACC-04 — Password rejection, rotation and session invalidation

```gherkin
Feature: Local password and session security
  Scenario Outline: Reject an invalid local password change without mutation
    Given a Local Database user has an active authenticated session
    When the user submits a change with "<input_condition>"
    Then the password change is rejected with safe inline and toast feedback
    And the stored password and session generation are not changed
    And an audit-only rejection uses reason "<reason_code>"
    And no password or secret value is written to audit or notifications

    Examples:
      | input_condition                 | reason_code                |
      | an incorrect current password   | current_password_mismatch  |
      | a new password equal to current | current_password_reuse     |

  Scenario: Rotate a valid local password and revoke other browser sessions
    Given the same disposable Local Database UAT user has sessions A and B
    And both sessions can access a protected KAORI workspace
    When the user successfully changes the local password in session A
    Then session A remains authenticated
    And session B is rejected on its next protected request
    And the old password can no longer authenticate
    And the new password can authenticate
    And a successful password-change audit event and user feedback are recorded
    And remembered sign-ins are subject to the same revocation boundary
```

**Evidence:** Human PASS for both rejection messages and the successful
two-browser rotation/revocation flow; isolated pytest checks no commit/session
mutation on rejection and session-generation implementation. A **second distinct
rejection audit-detail capture** (for reuse) and a standalone **CSRF browser
negative trace** were not supplied. Do not claim those independent checks PASS.

### SET-VIS-01 — Deterministic responsive/theme/three-tab visual contract

```gherkin
Feature: Responsive Account presentation
  Scenario Outline: Render Account in every canonical KAORI viewport
    Given the deterministic browser fixture has an authenticated local user
    And its personal authentication activity fixture has no events
    And the viewport is "<viewport>" with dimensions "<dimensions>"
    When the tester visits Profile, Activity and Credentials in light and dark
    Then the correct tab and workspace are displayed in each theme
    And there is no horizontal page overflow or clipped primary action
    And the activity empty state does not fabricate authentication events
    And HTMX pending feedback remains nonvisual with accessible status semantics
    And visual evidence is recorded without submitting a password

    Examples:
      | viewport       | dimensions |
      | large-desktop  | 1440x900   |
      | laptop         | 1280x800   |
      | compact-laptop | 1024x768  |
      | tablet         | 768x1024  |
      | mobile         | 390x844   |
      | small-mobile   | 360x800   |
```

**Evidence:** Operator-reported Playwright **6 passed, 66 deselected**; each
viewport test traverses both themes and all three Account tabs. Exact same-run
SHA was not included in that output. Separate nonempty event-table desktop
visual UAT was accepted at `295e4c84baf018d7df6630766e200cede2f7bd5f`.

### SET-OPS-01 — Account navigation, accessibility and recoverability

```gherkin
Feature: Account workspace operability
  Scenario: Preserve active tab through browser history and reload
    Given an authenticated user is on Settings > Account
    When the user opens Profile, Activity and Credentials in sequence
    And navigates with browser Back and Forward
    And refreshes the page
    Then the active tab, URL query parameter and visible workspace remain in sync

  Scenario: Keep HTMX, keyboard and network recovery usable
    Given the authenticated Account workspace is available
    When the user changes tabs with keyboard focus and Enter
    Then the focus indicator is visible and the requested tab opens
    When the user changes tabs under throttled network conditions
    Then HTMX navigation replaces the expected workspace
    And the loading status remains screen-reader-only, without a visual loading bar
    When network access is interrupted and then restored
    Then the workspace can be recovered and used again
```

**Evidence:** Operator-confirmed Human PASS for Back/Forward/Refresh, keyboard,
light/dark, offline recovery and tab navigation; DevTools screenshot shows
`htmx.min.js (xhr)`-initiated HTTP 200 navigation. Raw HAR, complete screen-reader
session and independent browser-failure trace were not archived.

### Gherkin-to-test and evidence traceability

| Scenario ID | Owning existing automated coverage | UAT evidence / limits |
| --- | --- | --- |
| SET-ACC-01 | `tests/contracts/settings/test_account_settings_redesign_contract.py` (profile/layout); `tests/ui/test_representative_interactions.py::test_settings_account_profile_activity_credentials_visual_qa` | Local/LDAP read-only profile screenshots: Human PASS; no live-provider health check |
| SET-ACC-02 | `tests/contracts/settings/test_account_settings_redesign_contract.py` (activity/layout); same Playwright browser test (mocked empty state) | Latest-five and Viewer deny/authorized audit: Human PASS; separate HTTP 403 header pending |
| SET-ACC-03 | `tests/contracts/settings/test_settings_uat_negative_boundaries.py::test_external_credentials_are_rejected_before_validation_or_password_access`; `tests/contracts/settings/test_account_credential_security_contract.py` | Local/LDAP credential ownership: Human PASS; contract-level external mutation rejection |
| SET-ACC-04 | `tests/contracts/settings/test_settings_uat_negative_boundaries.py::test_password_rejections_preserve_credential_and_session_state`; `tests/contracts/settings/test_account_credential_security_contract.py` | Rejection and two-browser session rotation: Human PASS; separate reuse audit detail and CSRF browser trace pending |
| SET-VIS-01 | `tests/ui/test_representative_interactions.py::test_settings_account_profile_activity_credentials_visual_qa`; `tests/ui/test_visual_audit_contract.py` | 6/6 browser parameterizations PASS; exact same-run SHA not recorded |
| SET-OPS-01 | Shared HTMX tab contract in `tests/contracts/settings/test_account_settings_redesign_contract.py`; read-only browser navigation in the visual QA test | Account history, keyboard, HTMX and offline recovery: Human PASS; full AT audit not claimed |

The Gherkin above is **documentation-only acceptance mapping**. Running existing
pytest commands continues to execute the actual regression tests; no BDD runner,
`.feature` parser, new fixture, provider mutation or official admission gate is
introduced. General Settings scenarios SET-GEN-01–04 remain separate and pending
their own negative/browser UAT evidence.

## 2026-10-24 — General Time Zone positive UAT and shared tab regression

The operator confirmed the five guided `SET-GEN-01` positive Time Zone checks:
manual Asia/Jakarta → Asia/Makassar and Save; preference persistence after Refresh;
automatic browser detection selection and Save; Detect Again without unintended
mode change; and the effective timezone shown in Account → Personal Presentation.
This is **Human UAT PASS for the positive browser journey**, not evidence of a
forged/invalid IANA value, explicit CSRF negative trace or canonical datastore
inspection. Invalid-IANA and CSRF-negative evidence remain pending.

For shared Settings query-backed tabs, the operator's screenshot showed the
phantom vertical scrollbar removed after #3032 / PR #3033. Their Dev Container
outputs report `djlint` PASS (0 changes), Settings Final Lock focused contract
**4 passed in 0.78s**, Settings Final Lock verifier **PASS (18 templates)**,
Notification Surface Style **PASS**, and existing General+Account six-viewport
Playwright cases **12 passed, 66 deselected in 107.50s**. Exact same-run local
SHA was not included in those terminal outputs; the shared tab fix was merged
to temporary holding at `c5f0e902905b957e43ba7569b28d540c50ffee94`.
The previous Account Human Acceptance remains unaffected; the General suite is
**not yet fully accepted** because SET-GEN-01 negative and SET-GEN-02–04
scope-specific evidence remain separate.

## 2026-10-24 — Account UAT evidence reconciliation

The Account portion of this matrix is **human accepted** for the tested functional, security, visual, and operational behavior. Acceptance is not equivalent to Full Admission or a complete screen-reader/DAST/CSRF assessment. Evidence was supplied through Dev Container terminal outputs and browser screenshots in the KAORI review conversation, then recorded in GitHub issue #2880. The accepted Activity table alignment refinement is governed by #3019 / merged PR #3020.

| Evidence / outcome | Observed result | Attribution / limitation |
| --- | --- | --- |
| Focused Settings negative/credential/lock/visual audit contracts | **25 passed** in 15.73 s; both Settings final-lock verifiers PASS | Dev Container holding `e026a44ba0c3a16578c4923327dbddfecb8ddd18`. Includes #3010 LocalProxy fixture fix; no official Full Admission. |
| Account Playwright deterministic UI | **6 passed, 66 deselected** in 71.10 s | Six canonical viewport parametrizations and light/dark/three-tab read-only navigation, operator output; exact same-run SHA not included. Browser setup initially blocked by missing Chromium/Linux dependencies and was subsequently repaired in the Dev Container. |
| Account Activity table visual and focused QA | **Human accepted**, `djlint` PASS, **14 passed** in 1.27 s, Settings Final Lock 18-template PASS, Notification Surface Style PASS | Exact operator-verified holding SHA `295e4c84baf018d7df6630766e200cede2f7bd5f`. Event / Source / Context / Result; Result column right-aligned. |
| Identity, Activity Audit permission, local/external credentials | **Human PASS** | Supplied local/LDAP screenshots and authorized/denied navigation; exact HTTP status response header for the direct Viewer denial not saved. |
| Local password negative and cross-session rotation | **Human PASS** for rejected UI, credential update, session invalidation, audit/toast feedback | Dedicated Local Database UAT account used for rotation; both rejected reasons observed in UI. Second distinct `account_security` rejection event detail and CSRF HTTP proof not supplied. No secrets posted. |
| Account SET-OPS-01 | **Human PASS** for Back/Forward/Refresh, keyboard Tab/Enter/focus, HTMX, light/dark, Offline/Online recovery | Browser screenshots show `htmx.min.js (xhr)` 200s and visible focus; operator explicitly confirmed history, keyboard and offline recovery PASS. Raw HAR/AT transcript not available; General Settings not rerun by this Account-only sequence. |

**Residual validation boundary:** General Settings negative/browser cases SET-GEN-01–04 are governed separately; do not convert those rows to PASS from Account evidence. A separate HTTP 403 response trace for unauthorized Activity Audit, a second rejected-password reason audit record and complete assistive-technology test were not supplied. These are evidence limitations, not newly established application failures. Do not repeat already accepted UAT unnecessarily; address any remaining gate only through scoped evidence or official admission when authorized.

**Delivery state:** implementation and human Account UAT completed in the temporary `kaori/review/staging-uat` holding track. No direct `main` edits, formal Developer Check/Full Admission, `kaori/staging` promotion, release or tag. Official CI/CD is **HOLD** pending explicit operator authorization. Existing local `app/static/css/output.css` modifications are separate from this documentation record.

Mark individual cases PASS/FAIL/BLOCKED only after actual execution and link
redacted screenshots/traces/logs with tested SHA, environment, date, reviewer,
expected/actual and follow-up issue. Tests run under fake identities must not
be presented as production-provider or end-to-end session evidence. Avoid
posting passwords or session cookies in GitHub evidence.

**No behavioral UI changes:** shared Violet Hero/cards/HTMX, default five-row
registry pagination and the previously approved no-visible-loading-bar design
remain authoritative. Exact-head Full Admission is a separate future
human-authorized step.
