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
| SET-GEN-02 | Regional Format locale/date/time selection | UI-only formatting; stored UTC and schedule authority unchanged | **Human PASS for positive flow (2026-10-24):** id-ID, year_month_day, 12h; persisted preview updates after Save, Refresh retention, Account locale consistency; independent canonical UTC/schedule mutation verification pending |
| SET-GEN-03 | System Information with and without `system.view` | No privileged tab/data disclosure; build metadata `Not supplied` truthful; no secret config echo | **Human PASS (positive/negative access boundary, 2026-10-24):** authorized metadata/capability view, truthful unknown build, no secrets, Viewer privileged tabs hidden, direct unauthorized tab falls back to Time Zone; raw HTTP trace not archived |
| SET-GEN-04 | Compatibility filter/reset/search, empty state, pagination 5, selected detail and no-JS | Filter/URL/result/focus correct, source-qualified version never equals live readiness | **Human PASS (2026-10-24, steps 1–8):** five-product registry, search, Extended-only MinIO, reset, selection/detail, empty state, URL/history/refresh and direct full GET; synthetic pagination contract exists, JavaScript-disabled fallback not separately tested; MinIO one-line copy Human Visual UAT PASS (2026-10-24), post-fix Ruff check and format check PASS (2 files already formatted; exact same-run local SHA not captured) |
| SET-ACC-01 | Profile local/external identity, RBAC role vs Super Admin | Read-only and source-backed identity; no false live provider readiness | **Human PASS (Account scope):** Local Super Admin and LDAP Viewer linked identity/profile screenshots; provider live-readiness was not asserted |
| SET-ACC-02 | Empty/five recent auth events and Activity Audit authorization | Five-event sample, safe status, IP proxy caveat, permitted drill-down | **Human PASS (UI/RBAC boundary):** local + LDAP event sample, Viewer denied at direct audit URL, authorized audit access; separate HTTP 403 header capture not provided |
| SET-ACC-03 | Credentials Local Database vs external provider | Password field only for local; external owner rejects change | **Human PASS (UI boundary):** local password form; LDAP provider-managed recovery without local form; automatic negative contracts also passed in focused suite |
| SET-ACC-04 | Incorrect current password, reuse, CSRF, session generation | No secret leakage; rejected no commit; on legitimate success current session remains, others revoked | **Human PASS (credential & session behavior):** both invalid password UI rejections, dedicated local UAT user successful rotation, old session revoked and current session retained, audit/toast; second rejection audit-detail evidence and independent CSRF browser capture remain pending |
| SET-VIS-01 | Account Profile/Activity/Credentials: six viewports, both themes, keyboard | No horizontal page overflow; shared tab focus/URL; no visual loading bars | **Operator automated PASS:** Playwright 6 passed, 66 deselected, 71.10 s after Chromium dependencies installed; exact browser-run SHA not independently captured |
| SET-OPS-01 | General/Account reload/back navigation, slow HTMX GET, accessibility | Nonvisual `sr-only role=status`, persistent controls/toast, no spinner/bar geometry | **Human PASS for both General and Account (2026-10-24):** General Back/Forward/Refresh, keyboard Tab/Shift+Tab/Enter and Offline→Online recovery 3/3 PASS; Account previously accepted; full assistive-technology/screen-reader audit not claimed |

## 2026-10-25 — Scoped CSRF HTTP assurance and Settings General UAT handoff

**Disposition:** Settings → General and Settings → Account Human UAT are **Accepted**
for all previously executed scenarios. The isolated CSRF route-function
regressions and automatic-mode browser check were already **PASS** at
`3ca2dac2217a54ebfb0b3411be5b10234d79f30c`. No confirmed Settings
functional defect remains that should block UAT of *another* workspace.

A final focused **HTTP-layer assurance** is added under child bug #3066,
reusing `tests/contracts/settings/test_settings_uat_negative_boundaries.py`.
The test creates an isolated Flask `test_client`, synthetic authenticated
session, and standard Flask-WTF CSRF token, without real account credentials.
It exercises the actual registered JSON route and login/CSRF gate:

| HTTP scenario | Expected status | State evidence |
| --- | --- | --- |
| Missing `X-CSRFToken` with otherwise valid session | `400 invalid_csrf` | Account timezone unchanged; no DB commit |
| Forged token with valid session CSRF state | `400 invalid_csrf` | Account timezone unchanged; no DB commit |
| Validly signed token from a different session | `400 invalid_csrf` | Account timezone unchanged; no DB commit |
| Valid signed token from the same session | `200 updated` | Synthetic timezone updated; exactly one mocked commit |
| No authenticated session | `401` or sign-in redirect `302` | Account timezone unchanged; no DB commit |

**First execution (operator-provided): FAIL — 23 passed, 1 failed
in 8.86s.** The only failure was
`test_browser_timezone_json_http_csrf_boundary[other_session-400-invalid_csrf]`
returning HTTP `200` instead of `400`. `ruff check` PASS,
`ruff format --check` requested formatting in this test file, and
Settings Final Lock verifier PASS (18 templates). No exact local
`git rev-parse HEAD` was pasted with this run.

**Root-cause review / bounded test correction:** the foreign CSRF token
was generated inside a nested `app.test_client()` context, potentially
reusing Flask-WTF's `g` token cache from the primary app context. The
test now obtains the foreign signed token in a **completed, separate
test-client context before** opening the primary client, and explicitly
asserts the tokens are different. This avoids false HTTP 200 caused by
test-fixture context reuse. All mutations remain mocked; no production
route or CSRF validation policy changed. Apply the operator-supplied
Ruff format adjustments for the same test module.

**Corrected HTTP regression: runtime PENDING** until the operator reruns
the following existing checks in Dev Container on the merged holding SHA:

```bash
git rev-parse HEAD
git status --short
python -m ruff check tests/contracts/settings/test_settings_uat_negative_boundaries.py
python -m ruff format --check tests/contracts/settings/test_settings_uat_negative_boundaries.py
python -m pytest -q -p no:cacheprovider tests/contracts/settings/test_settings_uat_negative_boundaries.py
python scripts/verify_settings_final_lock.py
```

Passing these tests will close the **targeted HTTP CSRF regression evidence
gap**, not certify arbitrary production-browser CSRF exploitability,
comprehensive DAST, independent scheduler/canonical UTC data mutation proofs,
or an end-to-end screen-reader evaluation. These are not prerequisites for
*starting a different page's local Dev Container UAT*; track each in its
respective governance/security workstream and keep official Full Admission
on HOLD until expressly authorized.

**QA handoff:** Existing General/Account Human Acceptance remains valid;
do not repeat approved UI/functional checks. Work may proceed to the next
requested KAORI page for local Dev Container UAT. The temporary
`kaori/review/staging-uat` branch is the aggregation target; official
CI/CD, `kaori/staging`, main, deployment, release and tagging stay HOLD.

## 2026-10-24 — Browser Time Zone JSON CSRF security remediation

**Scoped bug:** #3066 (child of #2880; link the native parent-child
relationship in GitHub Project when possible). Source audit found that
`app/static/js/user_timezone_sync.js` already submits a session-bound
`X-CSRFToken` from the shared app layout but the independent
`POST /settings/general/browser-timezone` handler did not validate it
before allowing the automatic-mode preference update. The form POST
contracts that passed earlier **do not cover this route**. This is a
confirmed **missing CSRF validation control**, not evidence of an
exploitable cross-site attack in a production browser: JSON preflight,
origin restrictions and production SameSite cookie settings remain
separate mitigations. Do not conflate either assessment.

**Scoped fix (runtime contract evidence PASS; full HTTP threat model still separate):**
reuse Flask-WTF `validate_csrf(request.headers.get('X-CSRFToken'))`
before reading JSON or invoking `sync_browser_timezone_preference`.
Missing/forged tokens return safe HTTP `400`,
`{"status":"invalid_csrf"}`; a valid signed session token preserves
the existing JSON `updated` response and automatic IANA sync.
No new middleware, JS fetch, session token format, external provider
calls, database migration, form UI or operational scheduling changes.

**Regression ownership:** added to existing
`tests/contracts/settings/test_settings_uat_negative_boundaries.py`:
missing-header and forged-header cases prove HTTP 400 and no mutation;
valid Flask-WTF session token proves one legitimate committed
automatic preference sync; client contract verifies shared layout
token and unchanged same-origin `fetch` header. The operator executed
focused regression and Settings Final Lock at the exact holding SHA
`3ca2dac2217a54ebfb0b3411be5b10234d79f30c`; results are recorded
below. These isolated tests verify route logic and commit control, but
do not replace raw authenticated HTTP/browser threat-model evidence.

```bash
git rev-parse HEAD
git status --short
python -m ruff check app/settings/routes.py tests/contracts/settings/test_settings_uat_negative_boundaries.py
python -m ruff format --check app/settings/routes.py tests/contracts/settings/test_settings_uat_negative_boundaries.py
python -m pytest -q -p no:cacheprovider tests/contracts/settings/test_settings_uat_negative_boundaries.py tests/contracts/settings/test_settings_final_lock_contract.py
python scripts/verify_settings_final_lock.py
```

**UAT boundary:** the operator reported enabling **Automatic Time Zone: OK**
in the dedicated browser UAT. This is Human PASS for activation of the
accepted automatic-mode flow; the message did not provide a before/after
stored timezone, redacted Network POST trace, or no-false-notification
capture, so exact timezone convergence is **not independently evidenced**.
Missing/invalid-token mutation rejection and valid-token update **PASS**
in isolated route-function contract tests; raw authenticated HTTP-negative
traces are separate. Do not expose user cookies or CSRF tokens. Previously
accepted SET-GEN-01–04/OPS flows remain unchanged. Full Admission,
staging/main and release HOLD.

### CSRF remediation — operator verification checkpoint

**Tested holding SHA:** `3ca2dac2217a54ebfb0b3411be5b10234d79f30c`
(confirmed identical to GitHub holding HEAD during evidence reconciliation).
`git merge --ff-only origin/kaori/review/staging-uat` reported
`Already up to date.`; the only reported worktree modification was
`M app/static/css/output.css`, unrelated to this remediation and
not changed by these GitHub commits.

| Focused quality check | Operator result |
| --- | --- |
| `ruff check` on JSON route and negative contract | **PASS — All checks passed!** |
| `ruff format --check` on same two files | **PASS — 2 files already formatted** |
| Focused Settings negative, Final Lock and General contract suites | **PASS — 34 tests in 8.95s** |
| `verify_settings_final_lock.py` | **PASS — Settings Final Lock v1, 18 templates** |
| Automatic Time Zone test-account browser check | **Human OK — Automatic mode enabled**; timezone before/after and HTTP mutation trace not supplied |

**Disposition:** issue #3066 CSRF validation implementation has passing
isolated executable regressions at an exact UAT holding SHA. The accepted
automatic UI mode remains functional in the operator's reported check.
A direct authenticated HTTP 400 (missing/forged CSRF), valid signed
token HTTP 200, browser automatic timezone change confirmation, and
broader security/DAST/assistive-technology assertions must not be inferred
from this contract suite. Any additional security-sensitive promotion
still requires the separately authorized official admission flow.

## 2026-10-24 — General operational final Human UAT and QA disposition

The operator explicitly confirmed **SET-GEN-OPS steps 1–3 PASS** on the
live Dev Container: navigating Time Zone → Regional Format → Compatibility
Versions followed by Back/Forward/Refresh kept URL, active tab and content
in sync; Tab/Shift+Tab/Enter keyboard traversal remained operable with
visible focus; and after forcing DevTools Network Offline, restoring Online
and Refresh recovered the General page without fabricated data. These are
human-confirmed browser observations rather than a captured network HAR or
full screen-reader assessment.

The operator also ran `python -m ruff format --check` on
`tests/contracts/settings/test_settings_uat_negative_boundaries.py`
and `tests/ui/test_representative_interactions.py`; the observed result
was **2 files already formatted — PASS**, resolving the remaining
formatter-only finding after PR #3061. The rerun message did not contain
a new local SHA; the earlier contract **15/15 PASS** and Playwright
**12/12 PASS** were captured at
`a0d412a3c925cbfa92236f21d296357c1bfe3ad4`. Settings Final Lock
**PASS (18 templates)** remains recorded from that earlier run.

**Disposition:** Settings → General functional/visual/operational Human UAT
is **Accepted** for completed SET-GEN-01–04 and SET-GEN-OPS 1–3. Focused
negative Flask-WTF and isolated browser regressions are PASS. Do not treat
this as official Full Admission, completed security threat-model review,
datastore/scheduler immutability proof, or comprehensive AT/DAST coverage.
Residual evidence includes the separate JSON browser-timezone endpoint's
CSRF/cross-origin security review, direct raw HTTP-negative traces where
needed, canonical UTC/schedule mutation verification and screen-reader
testing. No additional end-user reapproval of already accepted flows is
required. Official Developer Check, Full Admission, `kaori/staging`,
main promotion and release remain **HOLD**.

## 2026-10-24 — General negative boundary regression workstream

The following tests were added under existing QA issue #2880 **after** the
positive General acceptance. They test **isolated, nonmutating** negative
behaviors using Flask request contexts and the existing deterministic UI
fixture. The operator ran them on Dev Container SHA
`a0d412a3c925cbfa92236f21d296357c1bfe3ad4` with
`M app/static/css/output.css` as the only reported worktree modification.
The output supports **15/15 focused negative contracts PASS** (7 newly
parameterized cases and existing cases) in 7.74 s, **12/12 Playwright PASS**
(6 canonical viewports × 2 new scenarios, 78 deselected) in 33.88 s,
`ruff check` PASS and Settings Final Lock PASS (18 templates).
`ruff format --check` failed solely on the two test files' formatting
and the formatter-only follow-up was merged through PR #3061 under #2880.
The operator subsequently reran `ruff format --check` on both test files:
**2 files already formatted — PASS**. That rerun had no new local SHA output;
the earlier tests remain attributable to `a0d412a3c925cbfa92236f21d296357c1bfe3ad4`.

| Scoped concern | Regression test | Evidence state |
| --- | --- | --- |
| Forged manual IANA choice and invalid browser-provided IANA | `tests/contracts/settings/test_settings_uat_negative_boundaries.py::test_invalid_iana_timezone_submissions_preserve_saved_account_preference` (2 cases) | **Operator pytest PASS**; both rejected without saved timezone mutation or commit/audit |
| Missing CSRF token on actual Flask-WTF Time Zone and Regional Format forms | `tests/contracts/settings/test_settings_uat_negative_boundaries.py::test_general_preference_forms_reject_missing_csrf_before_any_mutation` (2 cases) | **Operator pytest PASS**; CSRF enabled in isolated Flask-WTF form validation; no commit |
| Browser timezone sync, manual/invalid/unchanged inputs | `tests/contracts/settings/test_settings_uat_negative_boundaries.py::test_browser_timezone_sync_denies_untrusted_or_unchanged_updates` (3 cases) | **Operator pytest PASS**; ignored/invalid/unchanged branches do not commit |
| True JavaScript-disabled Compatibility GET, filter and Reset | `tests/ui/test_representative_interactions.py::test_settings_compatibility_registry_without_javascript_uses_get_fallback` | **Operator Playwright PASS** across six viewports; isolated JS-disabled browser using authenticated fixture cookies |
| General keyboard Tab and Enter activation | `tests/ui/test_representative_interactions.py::test_settings_general_keyboard_tab_and_enter_navigation` | **Operator Playwright PASS** across six viewports; Tab focus and Enter navigation verified |

These tests do **not** independently certify persisted scheduler/canonical
UTC data, an external LDAP permission trace, all assistive technologies,
or the JSON `/settings/general/browser-timezone` endpoint's cross-origin /
CSRF threat model. The current Time Zone browser script uses local detection
and does not send a synchronization request on Detect Again; the dormant
JSON route must not be confused with the Flask-WTF form-post CSRF contract.

The operator additionally completed the three-step General operational
walkthrough (**Human PASS** for browser history, keyboard and Offline→Online
recovery). This is manual acceptance, not an archived HAR/network trace.
Full assistive-technology/screen-reader coverage, canonical UTC/scheduler
datastore proof, and review of the separate browser-timezone JSON endpoint
remain distinct evidence boundaries.

The following regression commands were exercised by the operator; rerun as
needed on the exact admission candidate SHA (the formatter rerun is PASS):

```bash
git rev-parse HEAD
git status --short
python -m ruff check tests/contracts/settings/test_settings_uat_negative_boundaries.py tests/ui/test_representative_interactions.py
python -m ruff format --check tests/contracts/settings/test_settings_uat_negative_boundaries.py tests/ui/test_representative_interactions.py
python -m pytest -q -p no:cacheprovider tests/contracts/settings/test_settings_uat_negative_boundaries.py
python -m pytest -q -s -p no:cacheprovider tests/ui/test_representative_interactions.py -k 'settings_compatibility_registry_without_javascript_uses_get_fallback or settings_general_keyboard_tab_and_enter_navigation'
python scripts/verify_settings_final_lock.py
```

If the no-JS browser run encounters a fixture/browser setup problem,
record the actual failure separately instead of substituting full GET
with JavaScript enabled. For the remaining General-only manual
accessibility/recovery evidence, use an isolated authenticated account and
test Tab/Shift+Tab/Enter, focus-visible state, Back/Forward/Refresh and
Offline/Online recovery on General tabs. Do not change real credentials,
run provider mutations or upload cookies/tokens.

## Settings → General — Gherkin acceptance specification

These General Settings scenarios record already accepted browser behavior and
the remaining boundary expectations as **non-executable** `Given–When–Then`
acceptance specifications. They reuse current pytest, UI and UAT taxonomy rather
than creating a BDD runner. A `Then` statement describes required behavior;
only the evidence notes below identify what was actually verified.

### SET-GEN-01 — Time Zone display preference

```gherkin
Feature: Personal timezone presentation
  Scenario: Persist a manual timezone without changing source data
    Given an authenticated KAORI user has opened Settings > General > Time Zone
    And the effective timezone is "Asia/Jakarta"
    When the user selects manual mode and chooses "Asia/Makassar"
    And saves the Time Zone preference
    Then the saved effective timezone is "Asia/Makassar"
    And the preference persists after browser refresh
    And Account > Personal Presentation shows the same effective timezone
    And the preference affects rendering, not canonical UTC or job schedules

  Scenario: Detect and save the browser timezone in automatic mode
    Given the account's Time Zone workspace is open
    When the user selects Automatic from browser and saves
    Then the mode is persisted as automatic
    When the user activates Detect Again
    Then the displayed detected timezone is refreshed from the browser
    And no unsaved manual preference is silently committed

  Scenario: Reject invalid IANA timezone evidence without updating state
    Given a Time Zone form with a previously saved valid IANA timezone
    When the user submits an invalid IANA timezone value
    Then KAORI rejects the update and displays safe validation feedback
    And the previous saved timezone is not overwritten
```

**Evidence:** Operator-confirmed steps 1–5 **positive functional PASS** on
2026-10-24. The invalid-IANA forged browser submission/CSRF-negative HTTP
trace and datastore/schedule immutability have **not** been independently
supplied; the last scenario remains a specification, not a completed Human UAT.

### SET-GEN-02 — Regional Format presentation

```gherkin
Feature: Account-specific regional presentation
  Scenario: Save locale, date pattern and clock convention
    Given an authenticated user is in Settings > General > Regional Format
    When the user chooses "id-ID" regional locale
    And selects the "year_month_day" date pattern and "12h" time format
    Then the current presentation preview still reflects saved preferences before Save
    When the user saves the regional preferences
    Then a success response is presented
    And the preview uses the saved new preferences
    And refreshing the page preserves the three selections
    And the account identity view shows locale "id-ID"
    And KAORI interface language remains unchanged

  Scenario: Preserve external and canonical time authority
    Given a user updates only their personal regional presentation preference
    When KAORI applies the preference to user-facing timestamps
    Then canonical UTC records and provider settings remain authoritative
    And operational schedules are not changed by this display preference
```

**Evidence:** Operator-confirmed five-step **positive functional PASS** on
2026-10-24. No independent datastore, canonical UTC, provider or scheduler diff
was supplied for the second scenario; do not elevate source-level design
boundaries into execution evidence.

### SET-GEN-03 — Read-only System Information authorization

```gherkin
Feature: Authorized read-only release reference
  Scenario: Show only safe release, build and capability metadata
    Given a KAORI user has "system.view" permission
    When the user opens Settings > General > System Information
    Then the release identity, environment and curated Capability Catalog are visible
    And unavailable build reference or date is labeled "Not supplied"
    And secrets, credentials and internal configuration endpoints are not exposed
    And a capability description does not claim live provider readiness

  Scenario: Fail closed when the current user lacks system.view
    Given an LDAP Viewer does not have "system.view" permission
    When the user opens Settings > General
    Then System Information and Compatibility Versions tabs are unavailable
    When the Viewer requests "/settings/general?tab=system-information" directly
    Then the request falls back to the authorized Time Zone tab
    And privileged release/capability metadata is not projected
```

**Evidence:** Operator-confirmed five-step **Human PASS**, including Viewer
direct-URL fallback. Focused negative route tests exist; no separate raw HTTP
response-header capture was archived. Later title Guide and compact copy
refinements were independently accepted as design.

### SET-GEN-04 — Qualified Integration Compatibility reference

```gherkin
Feature: Read-only compatibility registry and qualification details
  Scenario: Search, filter and reset the five-product reference catalog
    Given a user with "system.view" opens Compatibility Versions
    And the baseline registry lists Kubernetes, Prometheus, Thanos Query, Alertmanager and MinIO
    When the user searches for "Prometheus"
    Then matching results and their selection detail replace the registry results
    When the user clears search and filters Support Posture to "Extended only"
    Then only qualifying Extended-only providers appear
    And the MinIO release lifecycle remains "Upstream Archived"
    When the user activates Reset
    Then search and support filters return to their defaults
    And the five products are shown again

  Scenario: Preserve selected provider authority and empty-state meaning
    Given the complete compatibility catalog is displayed
    When the user selects MinIO
    Then the qualified versions and General Contract are displayed
    And KAORI support and upstream lifecycle are presented separately
    And the provider's Version Qualification is separate from Readiness Authority
    And qualification is not represented as live provider readiness
    When the user searches for "nonexistent-provider-123"
    Then "No matching integrations" is displayed
    And stale previously selected provider details are not displayed

  Scenario: Preserve search selection and URL across navigation and full GET
    Given the user has selected a compatibility result
    When the user uses browser Back, Forward and Refresh
    Then URL query, selected result and visible detail remain consistent
    When the user opens the result URL as a new browser document
    Then a full GET renders the same authorized compatibility view

  Scenario: Bound pagination and invalid query inputs
    Given a synthetic compatibility catalog with more than five products
    When the registry is projected at the first and later pages
    Then each page contains at most five products
    And invalid page, filter and selection inputs are normalized safely
    And an empty filter result does not retain an unrelated stale detail
```

**Evidence:** Operator explicitly confirmed **SET-GEN-04 steps 1–8 PASS**
and supplied the Extended-only MinIO screenshot. The live catalog has only
five products, so no visible second-page control is expected; the independent
synthetic 12-product projection contract covers pagination. Opening a URL in
a new browser tab established only full-document GET fallback. A subsequent
**JavaScript-disabled Playwright** run verified real native GET, noscript
Apply Filters, and Reset across six canonical viewport runs (PASS). The MinIO General Contract summary was subsequently
shortened under #2241 / PR #3050 to
`S3 reachability, bucket discovery, and optional object-storage governance.`
The operator explicitly confirmed that the revised text fits **one line
on the same desktop viewport** (**Human Visual UAT PASS**, 2026-10-24).
The acceptance is a direct user report; no new rendered screenshot was
attached to that confirmation. The existing 1–8 functional acceptance stands.

**Focused validation as submitted by the operator:** `ruff check` PASS;
`ruff format --check` reported **one unformatted file** and supplied its
exact single-line correction; Settings/Compatibility/Final Lock pytest
**19 passed in 7.85s**; Settings Final Lock verifier **PASS — 18 templates**.
The formatter-only issue #2241 follow-up PR #3053 was merged to temporary
holding at `ace88e961528978a61cf555129665d4ecc2bbc0e`, and the
post-merge source readback matches the exact Ruff suggestion. The operator subsequently provided a Dev Container rerun showing
`ruff check` **All checks passed!** and `ruff format --check` **2 files
already formatted** for the source and scoped contract file. The post-fix
formatting gate is therefore **PASS** based on operator evidence. No exact local SHA accompanied the previous operator
test output; it must not be retroactively attributed to a different commit.

### SET-OPS-01 — General tab operability and visual overflow

```gherkin
Feature: General Settings navigation and accessible tab strip
  Scenario: Keep General query-backed tabs usable in the canonical viewports
    Given the General Settings page uses the shared KAORI query tab component
    When the six canonical viewports are rendered in light and dark themes
    Then the tab strip has no unintended vertical overflow
    And narrow viewports retain horizontal scrolling between tabs
    And the selected tab and the visible workspace remain consistent

  Scenario: Preserve loading and keyboard behavior during General navigation
    Given an authenticated user navigates General Settings query tabs
    When the user follows a tab by keyboard, mouse or URL query
    Then the active tab and workspace correspond to the requested URL
    And HTMX partial requests use the existing nonvisual loading status
    And the authorized full GET fallback remains usable
```

**Evidence:** The operator reported existing General+Account six-viewport
Playwright **12/12 PASS**, Settings Final Lock **4/4 PASS**, shared verifier
PASS, and visual scrollbar removal after #3032. Account keyboard/history
and offline recovery UAT are accepted separately. Subsequently the General
operator **accepted all three General operational steps**: Back/Forward/Refresh,
Tab/Shift+Tab/Enter and Offline→Online recovery. This is not a comprehensive
screen-reader/assistive-technology certification or an archived network trace.

### General Gherkin-to-test and evidence traceability

| ID | Existing QA ownership | Evidence disposition |
| --- | --- | --- |
| SET-GEN-01 | `app/settings/general/actions.py`; `tests/contracts/settings/test_settings_final_lock_contract.py` | Five-step manual positive PASS; isolated invalid IANA and missing-CSRF contracts PASS; raw browser-negative HTTP traces pending |
| SET-GEN-02 | `app/settings/general/actions.py`; `tests/contracts/settings/test_general_settings_redesign_contract.py` | Five-step manual positive PASS; canonical data/schedule mutation evidence not supplied |
| SET-GEN-03 | `tests/contracts/settings/test_settings_uat_negative_boundaries.py::test_general_rejects_privileged_reference_tabs_without_system_view` and `::test_system_information_never_projects_unrelated_sensitive_configuration` | Five-step authorization/read-only Human PASS; raw HTTP header trace absent |
| SET-GEN-04 | `tests/contracts/settings/test_compatibility_registry_projection.py`; `tests/contracts/settings/test_general_settings_redesign_contract.py` | Eight-step Human PASS, synthetic pagination coverage and JS-disabled Playwright 6/6 PASS; MinIO one-line visual Human PASS |
| SET-OPS-01 | `tests/ui/test_representative_interactions.py::test_settings_general_query_tabs_keep_vertical_scroll_closed`; `tests/contracts/settings/test_settings_final_lock_contract.py` | General+Account viewport Playwright 12/12 PASS, General keyboard Tab/Enter Playwright 6/6 PASS, General operational steps 3/3 Human PASS; full AT pending |

These are acceptance **specifications only**. No `.feature` runner, new
step definitions, alternative test taxonomy or new official CI gate is
introduced. Existing negative-test gaps and exact-SHA limitations remain
visible. `SET-GEN-04` Human Acceptance is not a release or live provider
certification, and official Full Admission remains **HOLD**.

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

## 2026-10-24 — General System Information authorization UAT

The operator confirmed all five `SET-GEN-03` guided browser checks PASS:
an authorized account can read release identity, environment and capability
catalog; absent build SHA/date is honestly displayed as `Not supplied`;
System Information does not expose secret/configuration details; an LDAP
Viewer lacking `system.view` has neither System Information nor
Compatibility Versions tab; and directly requesting
`/settings/general?tab=system-information` as that Viewer falls back to
Time Zone without projecting privileged data. This matches the existing
fail-closed Settings route and focused negative contract; separate raw
Network/HTTP header evidence was not archived.

**Post-acceptance visual refinement:** issue #3040 / PR #3044 shortened three
System Information descriptions and added canonical title-level Violet
`Guide` Info Tips across all four General tabs. Source readback PASS and
merged to temporary UAT holding at
`f1cbc897c9e02603233007ce0b516311c408decd`. New copy layout and
hover/focus/touch visual QA on the operator's exact viewport remain pending;
the already accepted SET-GEN-03 permission/runtime results stand independently.

General `SET-GEN-04` Compatibility registry interactions, other scoped
negative evidence, and official Full Admission remain separate. CI/CD,
`kaori/staging`, main and release remain **HOLD**.

## 2026-10-24 — General Regional Format positive UAT

The operator confirmed all five `SET-GEN-02` steps **PASS** in a live
Dev Container browser: choosing `id-ID`; choosing `year_month_day`
(`2026-07-17` display example) and `12h`; observing the presentation
preview change on Save with success feedback; persistence after Refresh;
and Account Profile showing the persisted locale without changing the KAORI
interface language. The preview's pre-save persisted-value semantics were
also included in the operator-confirmed test steps.

**Evidence boundary:** these are human-confirmed browser observations, not a
datastore diff or an independently captured HTTP trace. The canonical UTC
data and operational job schedules must remain unchanged per approved design;
no separate database/scheduler-level proof was supplied with this run.
Negative tests for malformed or unauthorized regional values are not newly
claimed PASS. The user did not provide a new exact `git rev-parse HEAD` with
this browser run; do not attribute it to the later holding branch head.

**Status:** `SET-GEN-02` positive functional **Human UAT PASS**, while
At this **earlier** point General UAT was still in progress. Later
SET-GEN-03/04 and General operational UAT passed; remaining scoped advanced
security/AT evidence remains independent. Official CI/CD, Full
Admission, staging/main promotion, deployment and release remain **HOLD**.

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
The previous Account Human Acceptance remains unaffected. This paragraph
records the **earlier** UAT stage; subsequent SET-GEN-01–04 positive Human
Acceptance, General negative-contract/Playwright PASS and General operational
3/3 Human PASS supersede that stage. Residual security/AT evidence remains
separately tracked, not silently marked PASS.

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
