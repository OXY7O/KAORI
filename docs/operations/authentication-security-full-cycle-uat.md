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
