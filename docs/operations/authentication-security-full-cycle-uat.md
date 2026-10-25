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
