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
| SET-GEN-01 | Time Zone manual/automatic, Detect Again, invalid IANA | No implicit save, CSRF-safe background sync, correct display-only scope | Functional UAT approved; negative browser evidence pending |
| SET-GEN-02 | Regional Format locale/date/time selection | UI-only formatting; stored UTC and schedule authority unchanged | Functional UAT approved; runtime capture pending |
| SET-GEN-03 | System Information with and without `system.view` | No privileged tab/data disclosure; build metadata `Not supplied` truthful; no secret config echo | Source negative regression added; runtime pending |
| SET-GEN-04 | Compatibility filter/reset/search, empty state, pagination 5, selected detail and no-JS | Filter/URL/result/focus correct, source-qualified version never equals live readiness | Pure projection negative regression added; browser pending |
| SET-ACC-01 | Profile local/external identity, RBAC role vs Super Admin | Read-only and source-backed identity; no false live provider readiness | **Human PASS (Account scope):** Local Super Admin and LDAP Viewer linked identity/profile screenshots; provider live-readiness was not asserted |
| SET-ACC-02 | Empty/five recent auth events and Activity Audit authorization | Five-event sample, safe status, IP proxy caveat, permitted drill-down | **Human PASS (UI/RBAC boundary):** local + LDAP event sample, Viewer denied at direct audit URL, authorized audit access; separate HTTP 403 header capture not provided |
| SET-ACC-03 | Credentials Local Database vs external provider | Password field only for local; external owner rejects change | **Human PASS (UI boundary):** local password form; LDAP provider-managed recovery without local form; automatic negative contracts also passed in focused suite |
| SET-ACC-04 | Incorrect current password, reuse, CSRF, session generation | No secret leakage; rejected no commit; on legitimate success current session remains, others revoked | **Human PASS (credential & session behavior):** both invalid password UI rejections, dedicated local UAT user successful rotation, old session revoked and current session retained, audit/toast; second rejection audit-detail evidence and independent CSRF browser capture remain pending |
| SET-VIS-01 | Account Profile/Activity/Credentials: six viewports, both themes, keyboard | No horizontal page overflow; shared tab focus/URL; no visual loading bars | **Operator automated PASS:** Playwright 6 passed, 66 deselected, 71.10 s after Chromium dependencies installed; exact browser-run SHA not independently captured |
| SET-OPS-01 | General/Account reload/back navigation, slow HTMX GET, accessibility | Nonvisual `sr-only role=status`, persistent controls/toast, no spinner/bar geometry | **Human PASS for Account only:** navigation/history, HTMX XHR 200, keyboard/focus, light/dark, offline recovery; General/AT-specific coverage not claimed |

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
