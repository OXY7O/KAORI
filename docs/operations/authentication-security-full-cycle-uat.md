# KAORI — Authentication Security Full-Cycle Dev Container UAT

Authority: #3134 (TOTP/MFA), #3137 (Turnstile), #3138 (Access UI),
#638 (Security), #562 (MFA) and #3121 (single-active-session).

## Hard boundaries

Work ONLY on `kaori/review/staging-uat`. Do not launch official CI/CD, merge
into `kaori/staging` or `main`, or deploy to production. Human acceptance
requires actual browser evidence and a matching `git rev-parse HEAD`.
Both MFA and Turnstile change live login behavior when their administrator
policies are enabled; **do not activate without working break-glass recovery**.

Turnstile requires network access to
`https://challenges.cloudflare.com/turnstile/v0/siteverify` (backend) and
`https://challenges.cloudflare.com/turnstile/v0/api.js` (browser).
If CSP is enabled, admit exactly that script/frame/connection origin through
KAORI's existing security-header control; do not weaken CSP globally.

## Stage 0 — preflight and database

```bash
git status --short
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
git rev-parse HEAD
flask db current
flask db upgrade
flask db current
```

Run the migration against the **Dev Container UAT PostgreSQL database**, not
production. The migration extends the canonical singleton
`authentication_security_policies` row, stores the provider secret through
KAORI's `EncryptedText` key ring, and defaults Bot Protection to Disabled.
Preserve the already provisioned `INTEGRATION_CREDENTIAL_KEY`; never regenerate
an encryption key when factors or providers have been stored.

## Stage 1 — QA

```bash
ruff check app/access/authentication app/access/authentication_security app/settings/routes.py app/models/authentication_security.py tests/access/authentication/test_mfa_factor_primitives.py tests/access/authentication/test_bot_policy_runtime_contract.py tests/contracts/access/test_authentication_security_workspace_contract.py
ruff format --check app/access/authentication app/access/authentication_security app/settings/routes.py app/models/authentication_security.py tests/access/authentication/test_mfa_factor_primitives.py tests/access/authentication/test_bot_policy_runtime_contract.py tests/contracts/access/test_authentication_security_workspace_contract.py
djlint --check app/templates/access/authentication/partials/_login_form.html app/templates/access/authentication/bot_challenge.html app/templates/access/authentication_security/partials/_page_content.html app/templates/settings/account/partials/_mfa.html
python -m pytest -q -p no:cacheprovider tests/access/authentication tests/contracts/access
python scripts/verify_access_final_lock.py
python scripts/verify_settings_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```

No PASS until commands execute and the outputs are recorded at the same SHA.

## Stage 2 — TOTP enrollment and login

1. With Bot Protection **Disabled**, sign in as one test Local Database user.
   Confirm `Access → Authentication Security → MFA` is reachable for authorized
   administrators, and `Settings → Account & Authentication → MFA` is reachable
   by the individual user.
2. Start enrollment. Store the one-time manual seed securely in an authenticator
   app (Google/Microsoft Authenticator or any TOTP client), then submit a live
   six-digit code. Verify encryption-at-rest and that only hashed recovery
   codes persist. Save the displayed recovery codes in a password manager.
3. Sign out. Administrator changes MFA mode from Disabled to Optional, accepts
   revocation, then signs in with an enrolled account. Confirm a restricted
   `/auth/mfa` form appears after primary credentials and protected pages are
   denied until code success.
4. Enter an invalid code, replay a used code in the same 30-second step, expire
   the pending session and exceed challenge attempts. Each must fail, and
   no successful login audit / new session generation may result.
5. Enter fresh valid code. Protected page now opens; single-session replacement
   occurs only here. Sign out then use **one recovery code**, and prove that
   reusing that exact code fails.
6. Test `Required Privileged` and `Required All`, restricted enrollment
   for an unenrolled account, Local Super Admin recovery, provider-disable
   while MFA pending, logout, two-browser replacement and Remember Me.
7. In Settings, regenerate recovery codes with fresh primary reauthentication
   and an MFA proof, and verify previous codes are invalidated.

## Stage 3 — Turnstile provider setup and live test

1. Use an authorized Access administrator. Navigate to
   `Access → Authentication Security → Bot Protection`.
2. Keep Protection Mode **Disabled**. Set provider Cloudflare Turnstile,
   public sitekey, verification secret and exact browser hostname
   (`localhost`, `127.0.0.1` or the UAT DNS name as actually returned by
   Siteverify). The secret never appears in Activity Audit or GET forms.
3. Save configuration and use **Test Turnstile**. The backend performs live
   Siteverify and commits non-sensitive verification evidence only on success.
   An enable action **must fail** unless a matching configuration was tested
   successfully in the last hour.
4. Change mode to **Always**, acknowledge the operational impact and Save.
   Refresh anonymous login: the Turnstile widget must be visible. Submit login
   without a token or with a rejected token: credentials must not be checked
   and no authenticated browser session may be issued. Supply a fresh valid
   widget token: primary credentials are now processed and, when applicable,
   the MFA challenge follows.
5. Test SSO: clicking Google/GitHub begins at the KAORI bot-preflight form;
   a browser flow cannot reach the external provider start without a successful
   server-verified token. Callback verifies continuity of the challenged
   redirect; replay/expired grant must be denied.
6. Test failure and outage: denied Siteverify, hostname/action mismatch, token
   replay, expired token, timeout, blocked backend egress, and blocked widget
   script. All active-challenge paths must fail closed with sanitized errors.
7. Return mode to Disabled using an already-authenticated **separate** admin
   browser if necessary; confirm normal login resumes and audit records the
   policy transition.

**UAT dummy keys** (Cloudflare official and intentionally PUBLIC, never use in
production): passing visible sitekey `1x00000000000000000000AA`,
passing verification secret `1x0000000000000000000000000000000AA`.
Use failing sitekey `2x00000000000000000000AB` and matching failure
secret `2x0000000000000000000000000000000AA` for negative behavior.
The KAORI policy refuses enabling these keys outside Flask DEBUG/TESTING.
Testing secrets are **not** actual vendor credentials. For realistic hostname
checks and production-style acceptance, provision a genuine UAT Turnstile
instance in Cloudflare and use the host actually served by KAORI.

Cloudflare authority: https://developers.cloudflare.com/turnstile/troubleshooting/testing/
and https://developers.cloudflare.com/turnstile/get-started/server-side-validation/

## Evidence and security exceptions

Collect screenshots with usernames/emails/tokens/seeds/recovery codes and
secret fields **redacted**. Record signed-in/out Activity Audit, MFA factor
transition events and Bot Protection policy/verification outcomes.

CAPTCHA Adaptive mode and WebAuthn are NOT in this bounded deliverable. Native
session generation, account RBAC, existing notification/audit services and
external IdPs remain the source of truth.

Never mark full-cycle UAT PASS from unit tests, source review, or mock Siteverify.
Full Admission and promotion remain operator HOLD.


## UAT visual feedback extension — Assurance Overview (#3166)

Following the operator's 2026-10-25 screenshots, the Authentication Security Overview was redesigned without changing login enforcement or administrator form handlers. When running browser UAT, also verify:

1. Hero context has concise, **single-line desktop** MFA and Turnstile helper sentences without clipped/overflowed labels; mobile remains responsive.
2. **Authentication Assurance Posture** uses actual committed MFA mode (Disabled, Optional, Required Privileged, Required All), Bot Protection mode (Disabled or Enforced) and the existing session-generation behavior. Inspect two combinations: both optional protections disabled, then one enabled.
3. **Security Control Summaries** display corresponding state and link to the correct existing query-backed MFA, Bot and Session tabs; browser back and HTMX tab navigation still work.
4. **Operational Boundaries** distinguishes Access policy, user MFA enrollment under Settings, and primary Identity Provider management. No third-party health is guessed from configured credentials.
5. Verify desktop/mobile at standard and narrow widths, light/dark contrast, keyboard focus, no horizontal overflow, no policy-form regression, and meaningful no-JS GET navigation.
6. Run existing Jinja/Contract/DjLint checks against the exact reviewed branch SHA; **do not claim UI Human UAT PASS** from source-only results.

This is a presentation-only refinement under #3166; Database migration or re-enrollment is not required to review this UI diff. Previously migrated authentication schema is unaffected.

## Assurance Overview second visual QA checkpoint (#3166)

After the revised screenshot, inspect `Access → Authentication Security → Overview` for:
- A compact **Guide** trigger directly beside Authentication Assurance Posture. Desktop hover, keyboard focus, Enter/Space, Escape, touch/click and HTMX replacement follow `components/info_tip.html`; the popover is not clipped by its parent section.
- The **Security Control Summaries** heading has no permanent secondary text.
- The **Operational Boundaries** two columns each contain three aligned, scannable semantic rows (Governed Here vs Managed Elsewhere) rather than long unbalanced narrative paragraphs. Responsive stack/mobile and dark mode retain the same hierarchy.
- Policy/config status, CTA destinations and all MFA/Bot/Session non-Overview admin forms remain unchanged.
- Compare screenshot and command outputs against an exact `git rev-parse HEAD` value; no new database migration is necessary for these changes.

Regression QA: `djlint --check app/templates/access/authentication_security/partials/_page_content.html`, `python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_overview_refinement_contract.py tests/contracts/access/test_authentication_security_workspace_contract.py`, `python scripts/verify_access_final_lock.py` and `python scripts/verify_sidebar_navigation_standard.py`. No official admission without operator authorization.


## MFA tab administration UAT refinement (#3189)

The Access MFA page must be tested independently of account enrollment:

1. **Preflight:** Use the migrated Dev Container database, confirm exact `git rev-parse HEAD` and keep Bot Protection Disabled to isolate MFA behavior. Establish a local recovery Super Admin and an ordinary human UAT account; avoid changing MFA policy on production users.
2. **Read-only:** With `identity_providers.view` but without `identity_providers.manage`, verify MFA mode, Guide, all four mode descriptions and Settings enrollment link are visible, but **Save MFA Policy is absent**. Direct POST must be forbidden by server RBAC.
3. **Enrollment:** With the ordinary account, go to `Settings → Account & Authentication → MFA`, enter current password (Local), generate a one-time setup key, and confirm fresh TOTP; save the one-time recovery codes privately. Do not put OTP secrets or recovery codes in screenshots or audit attachments.
4. **Optional:** As an authorized security administrator, select **Optional**, acknowledge impact, save. **Expect logout** after the committed policy changes, because the session generation of every currently active user is revoked. Sign in again; enrolled accounts must challenge after primary credentials, unenrolled accounts need not challenge.
5. **Negative:** Try incorrect/expired/replayed OTP, reuse the same recovery code, browse protected pages while MFA is pending, refresh pending state after timeout and test Remember Me/second-browser replacement. A failed MFA attempt must not revoke the previously valid authenticated browser session.
6. **Mandatory:** Confirm selecting Required Privileged or Required All fails safely if no eligible Local Database Super Admin is enrolled. Only enable the required modes after recovering and testing that specific local authority. Unenrolled required users should enter restricted enrollment, not a normal logged-in workspace.
7. **Audit:** Verify meaningful MFA policy-change, enrollment, verification and recovery events without secret-bearing metadata; match actor/session correlation where full authentication is committed.
8. **Visual:** Compare MFA policy cards, form, Guide trigger, mode list and Account Settings CTA at desktop/mobile, light/dark, keyboard-only focus and non-JS GET. Existing top-level Hero and sidebar stay unchanged.

Focused test commands at the reviewed HEAD:

```bash
ruff check tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
ruff format --check tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
djlint --check app/templates/access/authentication_security/partials/_page_content.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_workspace_contract.py tests/access/authentication/test_mfa_policy_contract.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```

Policy save and OTP challenge are **not UAT PASS** from a screenshot alone. This tab refinement does not require any additional migration. Official Developer Check and promotion remain HOLD.


## MFA visual pre-UAT refinement — impact notice and equal panels (#3189)

Screenshot feedback requires the **Change Impact** panel to use the approved
KAORI warning semantic tone and a compact one-sentence description.
At desktop widths, confirm the sentence is easy to read without overflow,
and confirm the policy form and the right **Enforcement Modes** panel have
aligned top/bottom boundaries. Their responsive/mobile layout must remain
free of horizontal scrolling; verify both light/dark mode and keyboard focus.
The mandatory acknowledgement remains required and the Save policy workflow
is unchanged.

The scoped test `tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py`
locks the warning tokens, concise description, `items-stretch` layout and
unchanged MFA form authority. This refinement adds no database migration,
MFA factor change or session mutation; full functional MFA UAT remains a
separate human acceptance checkpoint.


## Save MFA Policy — durable feedback and Activity Audit UAT (#3208)

Before continuing into personal MFA enrollment, test **Access → Authentication
Security → Multi-Factor Authentication** with an authorized UAT admin.

1. Keep **Disabled** selected, acknowledge policy impact and press
   **Save MFA Policy**. Expect the **MFA policy unchanged** info toast on the
   MFA tab. Inspect Access Activity Audit for the distinct
   **MFA Policy Unchanged** entry; previous/new policy must both be
   `disabled`, actor must be the actual administrator, and no session
   revocation should occur. There must be no fabricated policy-change event.
2. Select **Optional**, acknowledge impact and Save. The policy/revocation/
   audit transaction must commit together. The browser should redirect to
   **Login** and show the **MFA policy updated** success toast **after the
   current administrator session has been revoked**. The old browser and
   Remember Me cookies must not regain authenticated access.
3. Sign in again, return to **Access → Activity Audit**, open the most
   recent **MFA Policy Changed** detail and inspect its immutable actor,
   `previous_policy_mode=disabled`, `new_policy_mode=optional`, session
   reference correlation and Access category. It must be presented as an
   Authentication Security Control, **not as User Signed In**.
4. Verify invalid CSRF/missing acknowledgement/unauthorized actor/mandatory
   policy without local recovery authority are denied; failures must not
   create any successful policy-change audit or success toast. A simulated
   DB commit failure must roll back the policy and session generation update.
5. After this administrator flow, go to **Settings → Account &
   Authentication → MFA** (also available from the **Open My MFA Settings**
   CTA) to review the personal TOTP enrollment and recovery screen.
   Full login challenge/recovery UAT remains a separate phase.

Focused regression:
```bash
ruff check app/access/authentication_security app/access/authentication/mfa/audit.py app/platform_operations/notifications/event_catalog.py app/platform_operations/notifications/normalization.py tests/access/authentication/test_mfa_policy_save_feedback_audit.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
ruff format --check app/access/authentication_security app/access/authentication/mfa/audit.py app/platform_operations/notifications/event_catalog.py app/platform_operations/notifications/normalization.py tests/access/authentication/test_mfa_policy_save_feedback_audit.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
python -m pytest -q -p no:cacheprovider tests/access/authentication/test_mfa_policy_save_feedback_audit.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_workspace_contract.py tests/access/authentication/test_mfa_policy_contract.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```

The existing `djlint --check` difference on the common page template is
separate outstanding formatting work; this fix does not change the template.
No new schema migration. Do not claim successful browser UAT based on test
source/earlier CI output; collect exact SHA, actual toast screenshot (without
secrets), audit detail and human acceptance. Official admission HOLD.


## MFA iconography screenshot checkpoint (#3189)

Before proceeding with the functional factor UAT, verify the updated
Access → Authentication Security → Multi-Factor Authentication tab:

- Three summary tiles visibly distinguish Current Policy, TOTP verification
  and Session Impact using the existing Lucide icon treatment.
- Each enforcement mode has its own small icon, but Disabled/Optional/Required
  mode semantics and the **Current** badge remain state-driven. Toggle the
  policy in a **safe UAT environment** to confirm active styling is not a
  static decoration.
- Authenticator App and Recovery Codes are clearly scoped to the self-service
  enrollment link; no TOTP seed, OTP or recovery plaintext is present.
- Existing warning Change Impact, acknowledgement, Save, Guide, role-gated
  form, equal panel alignment and Session Security navigation are preserved.
- Capture desktop/mobile, light/dark and keyboard focus images; check icons
  do not clip on narrow layouts, text remains readable without color and the
  Info Tip does not obscure the form.

Run the approved MFA tab contract, global Access lock, sidebar and djlint
checks on the exact review SHA. The icon change does **not** constitute
functional MFA enrolment/challenge UAT acceptance.


## Settings Account MFA self-service visual checkpoint (#3228)

This is a UI refinement for the **personal** MFA enrollment tab in Settings;
it does not change the Access administrator policy controls.

Before testing enrollment, confirm the selected account's actual MFA state
(Not Enrolled, Setup Pending, or Factor Enrolled), policy, and recovery-code
count. Compare the tab with sibling Account Profile, Authentication Activity,
and Credential Management: the same icon/header, compact posture cards and
responsive natural-height 7/5 action/context grammar must be visible.

1. On a local unenrolled UAT account, **Step 01** provides a constrained
   password field and Generate Setup Key. After a correct password, verify
   the manually provisioned secret appears only in the response and is
   marked no-store; never capture it in screenshots or CI artifacts.
2. **Step 02** provides a compact six-digit code field with numeric mobile
   keypad attributes, visible helper and Verify & Enable MFA. Invalid OTP
   must not enable the factor; a valid fresh OTP must commit enrollment.
3. For an external identity, the form omits the local-password control and
   shows fresh-provider-sign-in guidance. Server-side freshness enforcement
   remains authoritative.
4. Upon enrollment, the workspace displays a recovery-code regeneration
   action with constrained credentials and separate recovery-security context.
   Codes issued after confirmation or regeneration appear once only with a
   persistent warning; previously unused codes become invalid when rotated.
5. Verify desktop (1440-wide), narrow mobile (375-wide), light/dark,
   keyboard-only tab sequence, accessible field names, and no horizontal
   overflow. The Settings shared HTMX tab and nonvisual loading status
   remain intact; no new visible progress indicator.
6. Validate `djlint --check app/templates/settings/account/partials/_mfa.html`,
   focused `tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py`,
   `python scripts/verify_settings_final_lock.py`, and existing
   authentication factor regression tests at exact source SHA.

Do not record factor seeds, real OTPs, recovery codes, cookies or raw user
credentials as visual/Audit evidence. UI source readiness does not prove
human MFA challenge/recovery UAT PASS. Official CI/CD admission remains HOLD.


## Approved MFA Settings visual mockup — pre-factor UAT (#3228)

For `Settings → Account & Authentication → Multi-Factor Authentication`, verify the newly approved mockup at the exact `kaori/review/staging-uat` commit:

1. The Violet-soft header, title-adjacent canonical Guide, decorative smartphone/security icons, and accurate **Not Enrolled / Setup Pending / Factor Enrolled** badge are present.
2. Three semantic icon-led cards show **Factor Status**, **Security Policy**, **Recovery Codes** from committed user state—not invented counts.
3. On desktop, numbered Step 01 and Step 02 forms occupy the left 7/12 width while the guide fills the matching right 5/12 height; no large empty right-bottom area. On mobile the whole layout stacks with no overflow.
4. Password field remains bounded; the 6-digit code is a **single real `verification_code` control** with numerical keyboard, native form validation, autocomplete, helper association and spaced display. Six decorative boxes must not lead to six independently submitted fields.
5. No QR image or URI is asserted present: server supports manual setup key only. The one-time key and recovery codes must never appear in screenshot attachments; existing no-store server headers and fresh authentication remain unchanged.
6. Enrolled users still receive the existing recovery-regeneration action/context panel; verify after visual UAT using sanitized artifacts.
7. Re-run `ruff check` and `ruff format --check` on `tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py`, `djlint --check` on `app/templates/settings/account/partials/_mfa.html`, focused `pytest`, `scripts/verify_settings_final_lock.py`, and shared sidebar verifier. User's prior Dev Container execution had 1 failing TOTP security primitive `repr` test; this is tracked separately in issue #3237 and must be fixed before full functional MFA acceptance.

UAT cannot be marked PASS based solely on source review or mocked imagery. Official Developer Check, Full Admission and staging/main promotion remain HOLD.


## MFA Settings 1/2/3 screenshot feedback checkpoint (#3228)

At the reviewed Dev Container SHA check the three marked corrections: (1) MFA header background is the same neutral Account card surface as sibling tabs; (2) no redundant six-digit helper under the verification control; (3) the right column consists of a **single** full-height guide with four scannable steps and one plain final help line, not a bordered callout within another box.

Verify the confirmation input uses `tracking-widest` (Settings Final Lock approved) and still submits a single six-digit `verification_code` with keyboard/autocomplete and native validation. Check desktop/mobile, light/dark, screen reader label, Guide and all three existing MFA action POST forms, then run `djlint --check app/templates/settings/account/partials/_mfa.html`, `python -m pytest -q -p no:cacheprovider tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py tests/contracts/settings/test_settings_final_lock_contract.py`, and `python scripts/verify_settings_final_lock.py` at the exact reviewed SHA.

Do **not** mark Generate Setup Key functional UAT passed merely because the layout and contract render: backend safe feedback is tracked separately in #3251, with real local-user sign-in/password and DB evidence still required. Never screenshot generated setup keys or recovery codes.


## MFA personal enrollment QR and native toast checkpoint (#3261)

Before browser UAT, install pinned Python requirements (e.g. `python -m pip install -r requirements/base.txt` inside the Dev Container) and confirm exact holding SHA. No database migration is added.

1. On a fresh signed-in local UAT identity, open Settings → Account & Authentication → MFA. Enter current password and Generate Setup Key. The resulting state should be **Setup Pending**, not Enrolled. Verify a **top-right success Operational Toast** with committed Activity Audit indicator and **no generic inline info strip**. Activity Audit should have exactly the existing `mfa_enrollment_started` event, not a duplicate.
2. The one-time response must display both **Scan QR Code** and **Manual Setup Key**. Confirm the QR is an inline PNG data image that works with a TOTP-compatible authenticator and matches the manual key. Scan directly in-browser; **do not screenshot or paste the QR or manual secret into tickets/logs/test artifacts**. DevTools response should include `Cache-Control: no-store`, `Pragma: no-cache` and `Referrer-Policy: no-referrer`. No network request to an external QR site and no provisioning URI in browser URL.
3. Reload GET: setup image and manual secret must **not** reappear; pending state alone may remain. Regenerate if a key or QR has been exposed. Setup expires per the existing MFA service TTL.
4. Enter the authenticator's valid six-digit code, select Verify & Enable MFA. Confirm MFA is enabled only after verification, the success toast appears, and newly issued recovery codes are shown exactly once (never screenshot them).
5. For invalid password, expired CSRF/stale login, wrong OTP and DB error: show a safe error toast with no QR, no leaked secret, no fake successful audit or Notification Deck item. For recovered users, regenerate codes and check one-time semantics.
6. Test normal full-page POST and HTMX response when used, mobile/light/dark and accessibility. Run scoped Ruff/djlint/pytest, Settings Final Lock and sidebar standard at exact SHA. A source check alone is not human functional acceptance.

Keep official Developer Check, Full Admission, staging/main and release HOLD until operator acceptance.

## MFA stacked guide and paired enrollment forms — visual UAT (#3228, 2026-10-26)

This checkpoint supersedes earlier **enrollment-layout-only** expectations
that the four-step guide is a right-hand column next to two vertically stacked
forms. The accepted visual reference places:

1. The **How to Activate MFA** guide immediately below the three authoritative
   status cards, across the full content width, ordered 1→4 in a single row at
   wide desktop; 2×2 on medium widths and vertically on narrow screens.
2. **Step 01 Generate Setup Key** on the left and **Step 02 Verify Your
   Authenticator** on the right in the same balanced desktop row; cards stack
   on mobile with no horizontal overflow or clipped form controls.
3. The QR/manual key within Step 01 only after a successful fresh-session POST;
   the single 6-digit code and Verify & Enable MFA remain in Step 02. A success
   toast is shown without an extra inline success strip. Existing enrolled
   recovery regeneration layout remains unchanged.

**Developer check:** record work-branch SHA and holding-branch tested SHA
separately. Run `djlint --check app/templates/settings/account/partials/_mfa.html`,
`ruff check tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py`,
`ruff format --check tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py`,
`python -m pytest -q -p no:cacheprovider tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py tests/contracts/settings/test_account_mfa_enrollment_feedback_contract.py tests/contracts/settings/test_settings_final_lock_contract.py`,
`python scripts/verify_settings_final_lock.py`, and
`python scripts/verify_sidebar_navigation_standard.py`.
Rebuild the existing frontend if its configured template-content workflow
requires it, and use the existing Playwright/Visual QA harness with responsive
and theme coverage rather than adding a new test runner.

**Human browser UAT:** check desktop 1440×900 and 1280×800, tablet 768×1024,
and mobile 390×844/360×800; light/dark; keyboard-only focus; fresh enrollment
and pending behavior. On a safe disposable identity, verify valid and invalid
TOTP, wrong current password, retry/stale session, proper one-time QR/recovery
visibility, meaningful toast, audit correlation, and no duplicate audit event.
For *visual* evidence use the sanitized pending/non-secret rendering (or redact
the entire QR and key area before storing screenshots); never retain genuine
QR, manual seed, OTP or recovery codes in issue or CI artifacts.
Classify local execution as PASS/FAIL/BLOCKED/NOT RUN at its actual SHA;
no automatic Human Acceptance or official admission.

## MFA UAT-2 red-marked visual feedback and contract repair (#3228 / #3251, 2026-10-26)

Operator screenshot marks guide step 1 and step 2 descriptions (#1/#2) as wrapping and Current Password (#3) as narrower than Verification Code. Recheck at the selected Dev Container **holding SHA**: descriptions should read "Confirm your password or sign in again." and "Scan QR or enter the setup key.", fitting one line at the reviewed 1159px desktop image width but wrapping on smaller screens; Current Password and Verification Code should each span the available width of their Step 01/02 cards (not the entire page). Recovery regeneration sizing and the QR/manual-secret warning surface remain unchanged. Verify 1440×900, 1280×800, 1024×768, 768×1024, 390×844 and 360×800 in light/dark; confirm keyboard focus, form validation, pending/enrolled states and no overflow.

The provided previous run (before this correction) reported `ruff check` PASS, `djlint --check` PASS, Settings Final Lock PASS and Sidebar Standard PASS; `ruff format --check` FAIL in the MFA UI contract and pytest **25 PASS / 1 FAIL** because the feedback regression asserted the obsolete inline `mfa_feedback` name. The newer #3261 toast instead calls `message = _mfa_account_error_message(exc)` and emits a safe transient error toast. The bounded test fix under #3251 validates the live source pattern rather than reviving inline feedback; **do not ascribe the previous PASS values to the new SHA**.

Run focused exact-SHA QA again:
```bash
ruff check tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py tests/contracts/settings/test_account_mfa_enrollment_feedback_contract.py
ruff format --check tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py tests/contracts/settings/test_account_mfa_enrollment_feedback_contract.py
djlint --check app/templates/settings/account/partials/_mfa.html
python -m pytest -q -p no:cacheprovider tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py tests/contracts/settings/test_account_mfa_enrollment_feedback_contract.py tests/contracts/settings/test_settings_final_lock_contract.py
python scripts/verify_settings_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
Actual scan and authentication evidence must use a fresh rotated setup key; redact QR, manual seed, password, OTP and recovery codes from screenshots. Official admission remains HOLD until separately authorized.

## MFA enrolled recovery — symmetric panel UAT (#3228, 2026-10-26)

The operator approved a replacement recovery layout for the **enrolled** factor state; historical vertically stacked recovery input expectations above are superseded only for the enrolled view. On the exact holding SHA, navigate **Settings → Account & Authentication → Multi-Factor Authentication** using an authorized enrolled disposable/local test account:

1. Desktop (1440×900 / 1280×800): left Regenerate Recovery Codes and right Recovery Security cards have matching visible heights. The left has a single horizontal input + input + action row with label/accessibility preserved; the lower region shows three procedural steps. The right has three compact icon-labelled security statements, normally one line each if space permits. Do not shrink or clip text to manufacture this state.
2. Tablet/mobile (1024×768, 768×1024, 390×844, 360×800): both cards and all controls stack naturally with no horizontal scroll, clipped input or disappearing action. Check both light/dark themes and keyboard focus.
3. With local auth, Current Password must appear and remain required. With external/provider auth, no misleading Current Password control is rendered; fresh-login and TOTP/recovery verification remain required by the server. Inspect exact POST action `regenerate`, two required value names only when authorized, CSRF token and correct loading/toast/errors.
4. In an isolated authorized test identity, incorrect password/code must not regenerate codes, audit false success or leak secrets. Valid regeneration invalidates previously unused recovery codes and displays replacements only once, with the approved Operational Toast and Activity Audit correlation. Check that refresh cannot re-display one-time plaintext. Do not attach any QR, setup key, password, OTP or recovery code as evidence.
5. Record commands/actual outputs, source SHA, browser viewport/theme observations, redacted screenshots and Human Acceptance decision separately. Do not infer manual PASS from source contracts.

Focused regression (reuse existing gates):
```bash
ruff check tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py tests/contracts/settings/test_account_mfa_enrollment_feedback_contract.py
ruff format --check tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py tests/contracts/settings/test_account_mfa_enrollment_feedback_contract.py
djlint --check app/templates/settings/account/partials/_mfa.html
python -m pytest -q -p no:cacheprovider tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py tests/contracts/settings/test_account_mfa_enrollment_feedback_contract.py tests/contracts/settings/test_settings_final_lock_contract.py
python scripts/verify_settings_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
Official CI/CD admission remains **HOLD** until explicitly authorized.

## Enrolled recovery copy/header micro-refinement UAT (#3228, 2026-10-26)

After merging the scoped design, verify **Recovery Security** has a short secondary line below its title (“Review safeguards before replacing your recovery codes.”) and the first **Verify your identity** guidance item reads “Verify with a valid code.” The current password/code/Regenerate control row, left three-step strip, right security statements and full card-height symmetry must remain unchanged. Review the desktop reference around 1159/1280/1440 px, tablet 768 and mobile 360/390 in light/dark, with no forced nonwrapping or overflow.

Execute at the exact UAT holding SHA:
```bash
ruff check tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py tests/contracts/settings/test_account_mfa_enrollment_feedback_contract.py
ruff format --check tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py tests/contracts/settings/test_account_mfa_enrollment_feedback_contract.py
djlint --check app/templates/settings/account/partials/_mfa.html
python -m pytest -q -p no:cacheprovider tests/contracts/settings/test_account_mfa_enrollment_ui_contract.py tests/contracts/settings/test_account_mfa_enrollment_feedback_contract.py tests/contracts/settings/test_settings_final_lock_contract.py
python scripts/verify_settings_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
The user's earlier result of `26 passed` applies to a **previous MFA candidate**, not this updated design. Retain valid/invalid code, provider/local credential, one-time recovery, toast, audit and no-store Human UAT. Do not attach secrets or mark QA/Human Acceptance PASS before new exact-SHA evidence.

## Bot Protection approved Overview/MFA visual alignment UAT (#3299, 2026-10-26)

Visual redesign must be reviewed independently from any decision to enable the security policy. At the exact checked `kaori/review/staging-uat` SHA, verify **Access → Authentication Security → Bot Protection**:

1. The canonical Bot Protection heading/Guide and actual `Enforced` or `Not Enabled` badge match the committed `bot_mode`, not the visual mockup's illustrative Enabled state.
2. Three posture cards show **Protection Mode**, **Verification Adapter** (currently Cloudflare Turnstile), and **Provider Configuration**. `Not Configured` remains correct when credentials/hostname are missing; `Configured` is not equivalent to successful provider health.
3. On desktop, two equal-height panels show **Protection Configuration** (3/5 width) and **Activation & Safety** (2/5). Form fields have explicit labels, 44px controls, adaptive site-key/hostname columns and original endpoint; right-side guide is Configure → Test → Enable, with one short security footer. At tablet/mobile widths both panels and cards stack without horizontal scrolling or clipped Turnstile widgets.
4. In a manager session, Disabled/Always are the only choices. Save retains `csrf_token`, `provider_key=cloudflare_turnstile`, `site_key`, `hostname`, `secret_key` and the required impact checkbox. Secret remains write-only; viewer does not get a save/test form.
5. With a complete saved *Disabled* configuration, **Test Turnstile** appears and submits a genuine widget token only over its existing server route. For missing credentials, show guidance rather than a fake CTA. `bot_tested_at` proves evidence recorded but is not by itself a live Ready badge. Changing keys/hostname clears evidence; Always must fail unless a matching live Siteverify test was successful within one hour.
6. Validate fail-closed denied/expired/mismatched tokens, unavailable Cloudflare egress and provider downtime with a separate authorized break-glass administrator session; do not enable without a rehearsed recovery route. Check Local/LDAP/SSO, rate limit, login audit, logout and disabled rollback. Do not attach site/secret values, verification tokens or authenticated cookies to screenshots.

Reuse quality gates:
```bash
ruff check tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py
ruff format --check tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py
djlint --check app/templates/access/authentication_security/partials/_page_content.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/access/authentication/test_bot_protection_turnstile.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
Record exact SHA, command output, desktop/light-dark/mobile screenshots with secret fields redacted, error/empty/read-only states and positive/negative security gate evidence. User acceptance cannot be declared from the prior MFA QA output. Official Developer Check, Full Admission and promotion to `kaori/staging`/`main` remain on HOLD.

## Four-tab Authentication Security Role Registry Overview UAT (#3305, 2026-10-26)

The user-selected Role Registry visual standard is now the under-Hero summary layout for **Overview, Multi-Factor Authentication, Bot Protection and Session Security**. Verify that each tab starts with the same compact bordered icon/title/short explanation + source-backed status badge, followed by four metric cells and four smaller principle/boundary cards (responsive `md:2 / xl:4` layout). Do not infer live provider health, population, active-device count, completeness or required-factor coverage where the authoritative backend has not committed such evidence.

At an exact holding branch commit check browser widths 1440, 1280, 1024, 768, 390 and 360 in light/dark. Confirm accessible headings, visible focus, no horizontal scrolling or clipped labels, Info Tip Guide positioning and correct HTMX tab transitions. Check each tab in view-only vs manager sessions, configured/unconfigured bot instance, Disabled/Always, and all documented MFA policy modes. Preserve the existing original forms, CSRF, permission scopes, live Turnstile widget/test-before-enforcement, MFA policy revocation acknowledgment, and sign-in/failure handling.

**Runtime commands:**
```bash
git rev-parse HEAD
ruff check tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
ruff format --check tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
djlint --check app/templates/access/authentication_security/partials/_assurance_summary.html app/templates/access/authentication_security/partials/_page_content.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/access/authentication/test_bot_protection_turnstile.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
The operator previously reported **40 passing tests**, Access Final Lock and Sidebar Standard PASS on a previous Bot Protection SHA, with `ruff format --check` and `djlint --check` still failing. These are **not** new-SHA PASS evidence. Collect new output and assess formatter errors explicitly. Do not store secrets or Turnstile tokens in screenshots. Preserve separate provider-enabled functional/security UAT and explicit Human Acceptance; official admission HOLD.

## Authentication Security submenu above Hero — Navigation UAT (#3316, 2026-10-26)

Review the operator-approved placement change at exact `kaori/review/staging-uat` SHA. **Overview / Multi-Factor Authentication / Bot Protection / Session Security** must appear once as an existing KAORI **Tab Style 1 server submenu above the Hero**, *not* inside the rounded content card. Inspect 1440/1280/1024/768/390/360 light/dark, overflowing horizontal nav on mobile, active violet underline and `aria-current="page"`, keyboard/focus and tab-link fallback with HTMX disabled.

All four links must preserve real query URLs, update `#authentication-security-page` (including menu + Hero + active content) with normal HTMX, push browser history, and restore active state correctly with browser back/forward. Full reload, unauthorized/invalid `?tab=`, read-only viewers, management form POST routes and shared Activity Audit should remain unchanged; no nested secondary tabs should appear beneath the Hero. Check the existing Role Registry summary (four metrics + four governance cards) and MFA/Bot controls remain intact.

The previous candidate `ruff check`, Access Final Lock, Sidebar Standard PASS and 43/44 pytest PASS were not new SHA evidence; the one MFA test failure came from an obsolete `{{ current_mfa_label }}` direct text assertion after summary migration. The previous `ruff format --check` flagged three quote-only cases (Bot, MFA, four-tab contract). These source assertions and quotes have been updated in this scope, but **exact SHA execution is still required**. Existing `djlint --check` diff across many Jinja macro lines was reported; do not claim formatter PASS until exact-SHA output is clear.

```bash
git rev-parse HEAD
ruff check tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
ruff format --check tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
djlint --check app/templates/access/authentication_security/partials/_assurance_summary.html app/templates/access/authentication_security/partials/_page_content.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/access/authentication/test_bot_protection_turnstile.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
Keep prior UI/form/security acceptance separately evidenced, and never attach authentication secrets, Turnstile tokens or cookies.

## Authentication Security — remove redundant white wrapper and prevent governance wrapping (#3323, 2026-10-26)

In the exact UAT candidate after #3316, verify **all four Authentication Security tabs** render the page-level submenu above Hero, then individual Role Registry-style cards directly below the Hero without another white rounded shadowed container around the entire workspace. The individual assurance summary, three policy/control cards and Operational Boundaries panel retain their own border/radius/shadow, and the outer semantic `Authentication Security Workspace` section remains accessible.

At desktop 1440 / 1280 / the operator screenshot width (approximately 1150), the Overview compact governance statements for Provider Authority, Session Revocation and Committed Evidence should occupy **one complete readable line** with no clipped letters. Expected copy is: “Cloudflare validates Turnstile.”; “New logins revoke old sessions.”; “Audit tracks policy and logins.” On 1024/768/390/360 or zoomed views, natural wrapping is allowed; prohibit hidden overflow, ellipsis and horizontal scroll. Confirm right-side qualifiers, keyboard focus and light/dark contrast. All other tabs should preserve their forms, status badges, Guide, HTMX back/forward navigation, manager/view-only boundaries, and existing MFA/Bot security gates.

The operator's preceding log reported **45 focused pytest PASS**, Access Final Lock PASS, Sidebar Standard PASS and Ruff check PASS on the prior SHA; `ruff format --check` FAILED on the workspace contract and `djlint --check` FAILED on the large content template. The scoped Ruff formatting adjustments are included here, but these historical values **do not establish PASS on the new SHA**. Treat the large inherited djlint multiline-Jinja formatter diff as an open gate until the existing djlint formatter is run and reviewed; do not suppress validation or rewrite security semantics blindly.

Run at the new exact candidate SHA:
```bash
git rev-parse HEAD
ruff check tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
ruff format --check tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
djlint --check app/templates/access/authentication_security/partials/_page_content.html app/templates/access/authentication_security/partials/_assurance_summary.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/access/authentication/test_bot_protection_turnstile.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
Run the Visual QA and security-sensitive navigation/operation checks separately on the holding SHA. Record actual outcomes as PASS/FAIL/NOT RUN with sanitized evidence; no automatic human acceptance or promotion.

## Overview consolidated control areas — visual regression UAT (#3332, 2026-10-26)

The approved Overview composition after the separate **Authentication Assurance Posture** is now a single **Authentication Security Control Areas** card with icon/title/subtitle. Its body contains exactly three intact detailed control cards (Multi-Factor Authentication, Bot Protection, Session Security) with real status, review links and descriptions; below a subtle divider is **Operational Boundaries** with original Governed Here and Managed Elsewhere columns. There must be no separately bordered Operational Boundaries card and no page-wide white workspace wrapper. Other MFA, Bot Protection and Session Security tabs remain unchanged, with the canonical submenu above the Hero.

Verify at an exact SHA with 1440/1280/1024/768/390/360 widths, both themes, zoom and keyboard navigation: title precedes control cards, boundary section follows the three cards, card spacing/alignment is consistent, no horizontally clipped text or redundant border surface, and Overview links navigate to the correct server route with and without HTMX. Validate read-only vs manager permissions and that all existing security enforcement, CSRF, failed/valid Turnstile and MFA policy changes have unchanged behavior (don't enable Always without separate reviewed provider/recovery UAT). Record sanitized browser evidence; never include credentials, TOTP, recovery codes or Turnstile tokens.

The most recent operator-provided *previous SHA* output was Ruff check PASS, **Ruff Format FAIL** (workspace contract line 99), **djlint FAIL** (large template multi-line Jinja formatting), **47 pytest PASS**, Access Final Lock PASS, and Sidebar Standard PASS. The exact reported Ruff line has been changed to the formatter-proposed form, but new-SHA quality gate execution and djlint remediation remain pending unless independently evidenced. Do not infer PASS from earlier test results.

```bash
git rev-parse HEAD
ruff check tests/contracts/access/test_authentication_security_*contract.py
ruff format --check tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
djlint --check app/templates/access/authentication_security/partials/_page_content.html app/templates/access/authentication_security/partials/_assurance_summary.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/access/authentication/test_bot_protection_turnstile.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
Human Acceptance, official Developer Check, Full Admission, staging/main promotion and release remain on HOLD.

## Overview title outside box and harmonized Operational Boundaries UAT (#3338, 2026-10-26)

At the exact holding SHA review **Access → Authentication Security → Overview** after the separate Authentication Assurance Posture. The external **Authentication Security Control Areas** icon/title/one-line description must appear **above** the bordered common control box, not within its top border. The box should start immediately with the original three detailed control cards (MFA, Bot Protection, Session Security) and preserve all status labels, summary details and destination links.

The lower **Operational Boundaries** remains *inside that box*: one subtle dividing line with a soft background, icon/title/short description, and two symmetric inner bordered cards (**Governed Here / Managed Elsewhere**) that use the same spacing, radius and semantic surfaces as the control cards above. There must not be an independent full-bleed white table or a nested outer workspace shell. Verify at 1440/1280/1024/768/390/360 and 200% zoom, light/dark and keyboard: no awkward gaps, truncated labels, overflow or inaccessible headings. Check original ownership wording and true MFA/Bot/Session review URLs, with and without HTMX; verify unaffected MFA, Bot and Session tabs, manager/view-only permission boundary, and external security verification contracts.

The operator's previous 2026-10-26 run on a **prior commit** reported Ruff check and Ruff Format PASS, **48 pytest PASS**, Access Final Lock and Sidebar Navigation Standard PASS, while **djlint check still FAILS** for `_page_content.html` owing to extensive Jinja-macro and HTML indentation changes. Do not transfer previous successes to the new commit; `djlint` remains a verification blocker unless re-executed and fixed using the existing formatter. Do not enable provider `Always` merely to test the UI without documented independent recovery.

```bash
git rev-parse HEAD
ruff check tests/contracts/access/test_authentication_security_*contract.py
ruff format --check tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
djlint --check app/templates/access/authentication_security/partials/_page_content.html app/templates/access/authentication_security/partials/_assurance_summary.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/access/authentication/test_bot_protection_turnstile.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
Record source SHA, each command's actual results, redacted desktop/mobile screenshots, negative/positive authorization and browser behavior, and the human acceptance decision. Official admission, `kaori/staging`, main and release remain HOLD.

## Icon-free Overview heading and unified MFA detail layout UAT (#3344, 2026-10-26)

At exact `kaori/review/staging-uat` SHA, inspect Overview and MFA in the browser. **Overview** `Authentication Security Control Areas` must show only the title/subtitle above its existing bounded box; **no decorative heading icon/badge**, while all three control cards and harmonized two-column Operational Boundaries survive unchanged. **MFA** must have one external title/subtitle `Multi-Factor Authentication Controls` **above** one bounded card with original Policy Configuration + Enforcement Modes 3/2 grid, followed by an internal `Account Enrollment & Recovery` subsection with a dividing border, soft surface, one inset badge/action row and original Settings link. There must be no detached Enrollment card below the unified box.

Check 1440,1280,1024,768,390,360 widths, both color themes, 200% zoom, keyboard tabbing and screenreader heading/order; verify no clipping, double borders or excessive spacing and that both the manager edit form and read-only viewer render correctly. Exercise supported MFA policy choices with only authorized test users and preserve impact acknowledgement, session generation revocation, enrollment and recovery safety. Do not change policy or expose TOTP/recovery codes for visual testing. Retain HTMX query-tab navigation, URL history and native fallback. Check Bot/Session other-tab regression separately.

Earlier operator-reported **48 focused pytest PASS, Ruff/Ruff Format PASS, Access Final Lock PASS, Sidebar Standard PASS** were for a *previous SHA*; **djlint FAIL** on the large `_page_content.html` template was an unresolved existing formatting gate. Source modifications here do not prove new gate success. Execute the exact-SHA commands below and record evidence; review any formatter change without bypassing the original `djlint` command:
```bash
git rev-parse HEAD
ruff check tests/contracts/access/test_authentication_security_*contract.py
ruff format --check tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py
djlint --check app/templates/access/authentication_security/partials/_page_content.html app/templates/access/authentication_security/partials/_assurance_summary.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/access/authentication/test_bot_protection_turnstile.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
Collect redacted screenshots, actual command results, and Human Acceptance; defer Full Admission, `kaori/staging`/`main` promotion and release until explicitly authorized.

## Assurance copy and Bot Activation & Safety visual UAT (#3350, 2026-10-26)

Review the operator's four red-marked screenshots against the merged holding SHA. At ~1150-1200px desktop width, MFA **Factor Ownership**, **Factor Enrollment**, **Policy Transition** and Bot **Challenge Boundary**, **One-Use Proof**, **Activation Evidence**, **Recovery Access** each show a complete concise description on **one line**; at tablet/mobile 1024/768/390/360, accessibility zoom or different locale, text may wrap naturally, but cannot be hidden or clipped. Confirm titles and right-edge status/qualifier remain accessible and no layout/typography regression occurs on Overview and Session summary components.

In Bot Protection, verify the *two inline helper paragraphs* under Protection Mode and Verification Secret are absent, while labels, Disabled/Always options, encrypted password input, server save, CSRF, RBAC, Change Impact and mandatory recovery acknowledgement remain intact. Encrypted secret/audit guarantees remain operational despite removal of duplicate copy. Test both manager and read-only viewer.

Right-hand **Activation & Safety** at desktop has three ordered, well-proportioned steps distributed through panel height with semantic context surfaces, not empty oversized zones. Each step must show practical truthful configuration/one-use proof/recovery guidance. On narrow devices the cards stack; no overflow or compressed Siteverify widget. Where provider configuration exists, the conditional real Turnstile challenge/test form remains usable; where it does not, show the original truthful setup-prerequisite guidance, never fabricate a `Healthy` or `Ready` state. Preserve one-hour proof validity and fail-closed admission. The footer about external provider authority and independent recovery remains.

The operator's preceding **old SHA** evidence showed Ruff check PASS, **Ruff Format FAIL** (two test assertion formatting sites), **50 focused pytest PASS**, and earlier **djlint FAIL** on a large multiline Jinja formatting diff. This scope updates those two test-format locations but does not claim runtime success or eliminate the djlint debt. New-SHA Ruff, Ruff Format, djlint, pytest, Access Final Lock/Sidebar verifier, browser light/dark/responsive, security UAT and Human Acceptance **must be run and recorded**; do not waive formatter failure.

```bash
git rev-parse HEAD
ruff check tests/contracts/access/test_authentication_security_*contract.py
ruff format --check tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py
djlint --check app/templates/access/authentication_security/partials/_page_content.html app/templates/access/authentication_security/partials/_assurance_summary.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/access/authentication/test_bot_protection_turnstile.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
If `djlint --check` still reports the inherited macro/markup layout diff, review and apply only the standard `djlint --reformat` output on the existing file in the Dev Container, inspect its diff and re-run original gates. Do not disable checks or infer pass from structurally balanced tags. Official admission/kaori/staging/main remains HOLD pending user visual acceptance.

## Bot Protection unified controls hub — exact-SHA Visual/Security UAT (#3356, 2026-10-26)

Verify the current holding SHA in **Access → Authentication Security → Bot Protection**. The separate **Bot Protection** posture summary remains above a small external text-only **Bot Protection Controls** title and one-line subtitle (no heading icon). The title must occur *before* and label a **single bounded container** holding **Protection Configuration** and **Activation & Safety** side by side at desktop 3:2 (unchanged internals), then stacking on smaller widths. No additional global white workspace wrapper or inner-level duplicate title should appear. Compare spacing, border/radius, card hierarchy and Violet semantic surfaces with the already accepted MFA unified controls section.

Inspect 1440/1280/1150/1024/768/390/360 widths, both light/dark themes, 200% zoom, keyboard order, heading semantics, focus rings, no horizontal clipping, mobile stacking and equal-height appearance. Manager retains genuine CSRF-protected Save Bot Protection form; viewer sees read-only explanation. Protection Mode only offers Disabled/Always. Existing Test Turnstile is present **only** if permissions and complete configuration allow it; no fake readiness/success when unconfigured. Check provider config saving while Disabled, real one-use Siteverify test, proof freshness limited to one hour and unchanged credentials, Always fail-closed and independently approved administrator recovery using authorized UAT accounts; do not expose site secret, Turnstile token, passwords, recovery codes or session cookies in evidence. Three Activation & Safety steps, context cards and bottom provider-authority/recovery footer stay intact.

Previous operator evidence (older SHA): focused **53 pytest PASS**, Access Final Lock PASS, Sidebar Standard PASS; Ruff/Ruff Format previously PASS and **djlint --check still FAIL** on broad existing Jinja formatting in `_page_content.html`. This is NOT new-SHA QA. Run the standard commands below at the new holding commit. If djlint still fails, review/apply only the existing formatter `djlint --reformat` and rerun unchanged gates; no custom validator or bypass.

```bash
git rev-parse HEAD
ruff check tests/contracts/access/test_authentication_security_*contract.py
ruff format --check tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py
djlint --check app/templates/access/authentication_security/partials/_page_content.html app/templates/access/authentication_security/partials/_assurance_summary.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/access/authentication/test_bot_protection_turnstile.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
Collect each command's **actual** exit status, redacted screenshots, Visual QA and explicit Human Acceptance. Official Full Admission, `kaori/staging`, `main`, and release remain HOLD.

## Four-tab shared internal headers — UAT and quality gate (#3366, 2026-10-26)

On `kaori/review/staging-uat` at the **exact reviewed SHA**, verify all tabs **Overview / Multi-Factor Authentication / Bot Protection / Session Security**. Under each separate Role Registry-like committed assurance summary, the external text-only section title and explanation must remain unadorned. The bounded control box directly beneath must have the shared **icon + title + short description + committed status chip** internal header with a subtle divider, matching **Authentication Assurance Posture**. Check consistent header height, badge placement, light/dark Violet tokens, no duplicated `h2` IDs, responsive stack (sm/390/360), screenreader headings and non-truncated status values.

Expected values: Overview **Controls Enabled** or **Optional Controls Disabled** from actual MFA/Bot enforcement; MFA **Policy Active/Disabled**; Bot **Enforced/Disabled**, not provider healthy; Session **Generation Active**. Overview's three detailed cards and ownership matrix, MFA's protected policy form and private recovery links, and Bot's protected provider setup plus conditional real Siteverify test, one-hour unchanged-config evidence and independent-recovery warnings must be unchanged. **Session** gains only an informative read-only hub with **Governed in Access** and **Outside Current Scope**. Verify no form, action, idle/absolute timeout enforcement claim or active-device inventory is introduced.

Use manager/read-only test accounts, check HTMX tab switching/back-forward and full navigation, light/dark, 1440/1280/1150/1024/768/390/360/200%-zoom, and capture sanitized evidence. Do not expose MFA codes, Cloudflare secrets, provider tokens or cookies. Security-sensitive changes (MFA/Bot/session admission) must not be judged UAT PASS based on HTML-only smoke checks. Explicit Human Acceptance required.

The operator-supplied **previous SHA** results are `ruff check` PASS, **`ruff format --check` FAIL** in `test_authentication_security_bot_tab_ux_contract.py` and `test_authentication_security_overview_refinement_contract.py`, **`djlint --check` FAIL** with extensive prior Jinja/multiline template formatting in `_page_content.html`, **54 focused pytest PASS**, Access Final Lock PASS and Sidebar Navigation Standard PASS. The two exact Ruff source changes suggested by the formatter were committed under this issue. No Ruff/pytest/djlint checks on the new SHA have been executed by the GitHub connector; `djlint` remains OPEN until run and fixed using the existing standard formatter. Do not suppress checks or infer pass.

```bash
git rev-parse HEAD
ruff check tests/contracts/access/test_authentication_security_*contract.py
ruff format --check tests/contracts/access/test_authentication_security_*contract.py
djlint --check app/templates/access/authentication_security/partials/_page_content.html app/templates/access/authentication_security/partials/_assurance_summary.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/test_authentication_security_workspace_contract.py tests/contracts/access/test_authentication_security_mfa_tab_ux_contract.py tests/contracts/access/test_authentication_security_bot_tab_ux_contract.py tests/contracts/access/test_authentication_security_role_posture_tabs_contract.py tests/contracts/access/test_authentication_security_overview_refinement_contract.py tests/access/authentication/test_bot_protection_turnstile.py
python scripts/verify_access_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
```
If `djlint --check` still fails, use the already standard `djlint --reformat` on only the affected partial in a scoped formatter remediation work branch, review all formatting-only lines and rerun the original checks. Official Full Admission, `kaori/staging`, `main`, release remain HOLD.
