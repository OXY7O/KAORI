# KAORI — Authentication Security Full-Cycle Dev Container UAT

Authorities: #562 (MFA), #638 (Security), #641 (human/break-glass), #3121 (single-session), #3134 (MFA-02), #3135 (Bot Protection), #3137 (BP-02), #3138 (Access UI).

**Scope:** Local/LDAP/SSO primary authentication plus KAORI-owned optional/required TOTP MFA, one-time recovery codes and Cloudflare Turnstile provider configuration/enforcement. Local Dev Container review only; official Developer Check/Full Admission and release admission are HOLD.

## Deployment safety

Do not merge into production or enable mandatory MFA/Bot Protection without signed human acceptance and a rehearsed recovery method. Both policies default to **disabled** in committed database state. A source-controlled adapter alone is not provider readiness.

1. Protect and back up the database before running schema upgrades. Follow the approved KAORI deployment procedure for your environment.
2. The existing `INTEGRATION_CREDENTIAL_KEY` (and governed previous-key rotation) is used by the approved `EncryptedText` credential-protection mechanism to encrypt TOTP seeds and Turnstile secrets at rest. Do not print or submit its value to an issue/chat. Missing encryption material prevents enrollment/verification and must not be bypassed with plaintext.
3. The new Alembic chain is `20261023_delivery_identity → 20261025_mfa_storage → 20261025_bot_protection`; check its integrity before applying.
4. Run upgrade inside the Dev Container using the existing Flask app/environment and PostgreSQL. Never run direct `db.create_all()` as a migration substitute.
5. Keep normal Local Super Admin access and a controlled server-shell recovery path available before activating Always/Required policy.
6. Cloudflare Turnstile requires outbound HTTPS access to `challenges.cloudflare.com` for Siteverify, plus browser delivery of its challenge script/iframe. Its availability cannot be inferred merely from saved keys.

## Source checkout, migration and targeted QA

```bash
git status --short
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
git rev-parse HEAD

python scripts/verify_migration_graph.py
flask db current
flask db upgrade
flask db current

ruff check \
  app/access/authentication \
  app/access/authentication_security \
  app/settings/routes.py \
  app/models/authentication_security.py \
  app/commands/authentication_security.py \
  tests/access/authentication \
  tests/contracts/access/test_authentication_security_workspace_contract.py

ruff format --check \
  app/access/authentication \
  app/access/authentication_security \
  app/settings/routes.py \
  app/models/authentication_security.py \
  app/commands/authentication_security.py \
  tests/access/authentication \
  tests/contracts/access/test_authentication_security_workspace_contract.py

djlint --check \
  app/templates/access/authentication \
  app/templates/access/authentication_security \
  app/templates/settings/account/partials/_mfa.html

python -m pytest -q -p no:cacheprovider \
  tests/access/authentication \
  tests/contracts/access/test_authentication_security_workspace_contract.py \
  tests/access/identity_providers/test_provider_session_revocation.py

python scripts/verify_sidebar_navigation_standard.py
python scripts/verify_access_final_lock.py
python scripts/verify_settings_final_lock.py
python scripts/verify_migration_graph.py
```

Capture exact SHA and full stdout/stderr, including migration graph and DB-head output. Other existing auth/Settings/security/DAST gates remain necessary before Full Admission.

## 01 — Baseline and default-deny policy activation

1. Start KAORI on the migrated Dev Container database. Confirm Access → Authentication Security contains Overview, MFA, Bot Protection and Session Security.
2. Confirm MFA policy **Disabled**, Bot Protection **Disabled**, and Turnstile configuration **Not Configured**. The UI cannot claim active provider readiness before configuration.
3. Confirm ordinary Local sign-in with and without Remember Me still works as before; authentication audit shows normalized actor/source/session reference.
4. Confirm an account lacking `identity_providers.view` cannot visit the administrative page (403). An account without `identity_providers.manage` cannot POST either configuration mutation (403).
5. Verify regular users can reach Settings → Account & Authentication → Multi-Factor Authentication for their own factor only.

## 02 — TOTP enrollment and optional-policy sign-in

1. In Access → Authentication Security → MFA, set **Optional** with explicit session-revocation acknowledgement. Sign in again if policy change revoked your session.
2. Open Settings → Account & Authentication → MFA. Click **Generate Setup Key**. Local users must enter their current password; external accounts require a fresh authenticated session.
3. Store the displayed manual Base32 setup key only in the test authenticator. Do not screenshot it or retain it in Activity Audit. The setup expires after ten minutes.
4. Confirm a six-digit TOTP. A factor is active only after this confirmation. Save eight one-time recovery codes (plaintext shown once). Capture **redacted** evidence with the codes and setup secret hidden.
5. Log out, sign in again through Local DB; expect a restricted **Verify Your Sign In** challenge before authenticated app access and before generation issuance.
6. Enter an incorrect code; no authorized page should be accessible, and the event should show a failed MFA challenge without impersonating an authenticated actor.
7. Enter a valid *new* TOTP (a code already consumed during enrollment cannot be replayed). Expect authenticated access. Verify one successful sign-in and distinct MFA verification audit events.
8. Attempt the same code during the same TOTP step after a second primary login; expect replay denial until a fresh code.
9. Repeat with one recovery code: it must work once, then fail on reuse. Regenerate codes from the Account MFA page after current-password and factor verification; old unused codes must become invalid.
10. Disable MFA when policy is Optional, using current password and a valid factor. Then verify subsequent login requires no TOTP for that user.

## 03 — Mandatory MFA and lockout safety

1. Enroll an active Local Database Super Admin before enabling Required policy.
2. Select **Required for privileged accounts**. Verify the control refuses activation if no active Local Super Admin has a verified factor. Existing sessions are revoked atomically on policy change.
3. A new privileged user without a factor must land on restricted enrollment after primary auth, not normal KAORI application.
4. Confirm that incorrect/enrollment-expired OTP cannot issue a browser session. After successful enrollment, display recovery codes once and enter application.
5. Optionally test Required for all users with a disposable set of UAT identities. External LDAP/SSO enrollment and step-up require real configured providers and explicit evidence.
6. Rehearse lost-factor recovery using the authorized server shell (below). Confirm affected sessions are revoked and mandatory users must re-enroll.

## 04 — Turnstile provider configuration and enforcement

1. Create a Turnstile widget for the Dev Container hostname in the official Cloudflare dashboard. Use environment-appropriate test keys if available. Do not share the secret in chat or screenshots.
2. In Access → Authentication Security → Bot Protection, enter Site Key (public), Allowed Hostname (without scheme/port), Verification Secret (stored encrypted); save first as **Disabled**.
3. Confirm the UI says Configuration **Present**, not **Verified Connected**. Reopen page: secret input remains blank even though configuration remains present.
4. Change enforcement to **Always** only after making sure server-shell recovery is accessible; this revokes pre-enforcement login sessions. The subsequent login page must render the Turnstile widget and permit external script/iframe only through the scoped CSP.
5. Submit credentials without a valid token, with an expired or reused token, and during provider/network outage. Expected: **fail closed** before credential or SSO admission. No credential or token leaks into Activity Audit.
6. Complete a valid challenge then Local login; if MFA enrolled, second factor is still required. The successful MFA completion then issues the one active login generation.
7. Exercise SSO: legacy GET `/auth/sso/<provider>/start` must not initiate SSO when Always is active; the CSRF-bound challenged POST from login should initiate the provider redirect.
8. Verify source-address, hostname/action mismatch, unexpected verifier response, timeout, and Cloudflare error paths using existing injected-transport tests and optionally UAT fault injection. No token is reusable.
9. Switch Bot Protection to Disabled, confirm ordinary sign-in works again. Verify auditable policy change events. Do not treat Disabled as protection.
10. Adaptive scoring and hCaptcha are intentionally separate, not active in this initial Turnstile full-cycle.

## 05 — Server-side recovery and break-glass

These commands are **not exposed via HTTP** and require approved shell/operational change control. They record a system-scoped audit event with the shell username and a bounded incident reason; that evidence alone does not replace human change acceptance.

```bash
# If Turnstile outage locks out all interactive sign-ins:
flask disable-bot-protection --reason 'KAORI-UAT-SECURITY-RECOVERY' --yes

# If a human user loses the enrolled second factor:
flask reset-user-mfa --username '<uat-username>' --reason 'KAORI-UAT-MFA-RESET' --yes
```

A mandatory-policy user with a reset factor is **not** silently allowed into the application; primary authentication leads to controlled re-enrollment. Confirm the operation produces evidence and invalidates the target's previous session generation.

## 06 — Full-cycle security regression and review

- Two independent browsers, Remember Me generation revocation after new successful MFA login, failed MFA preserving the earlier valid session until proof succeeds.
- TOTP enrollment expiration, last-used-step replay protection, recovery-code single consumption, secret encryption, no secrets in logs/evidence, strict CSRF/rate limits.
- Policy changes + password change + provider disablement; no resurrection of old remembered cookies.
- Normal/privileged/external identity boundaries and Local Super Admin recovery.
- UI: Violet light/dark, 14-inch desktop/mobile, focus and aria labels, GET/HTMX tab replacement, browser back/forward, responsive content, no disabled fake status.
- Real Cloudflare Siteverify, real PostgreSQL migrations/locking, negative SSO/LDAP routes, CSP/Cross-origin behavior and DAST require actual runtime evidence; authoring tests or source merging is **not** UAT PASS.

## Delivery / acceptance

Issues #3134 and #3137 remain open until this full-cycle evidence and Human Acceptance pass. Official Developer Check, Full Admission, `kaori/staging`, `main`, tags, deployments and production security-policy activation remain HOLD until separately authorized.
