# Authentication Security — Dev Container UAT

Authority: MFA #562/#3133/#3134, Bot Protection #3135/#3136/#3137, Access UI #3138, security #638.

## Runtime / acceptance boundary

This is an **administrative read-only review**. It does not enable any MFA, CAPTCHA, secret provider instance or provider-backed verification on login. The source-driven Turnstile verifier and MFA policy functions are staged for their separate activation workstreams. The existing Local/LDAP/SSO sign-in, Remember Me, generation revocation and Activity Audit must not change.

Execute on `kaori/review/staging-uat` after confirming a clean local tree. Do **not** run official CI/CD, staging promotion, deployment or release.

## Obtain exact UAT source

```bash
git status --short
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
git rev-parse HEAD
```

Record the exact HEAD alongside all command outputs.

## Focused QA

```bash
ruff check \
  app/access/authentication/mfa \
  app/access/authentication/bot_protection \
  app/access/authentication_security \
  tests/access/authentication/test_mfa_policy_contract.py \
  tests/access/authentication/test_bot_protection_turnstile.py \
  tests/contracts/access/test_authentication_security_workspace_contract.py

ruff format --check \
  app/access/authentication/mfa \
  app/access/authentication/bot_protection \
  app/access/authentication_security \
  tests/access/authentication/test_mfa_policy_contract.py \
  tests/access/authentication/test_bot_protection_turnstile.py \
  tests/contracts/access/test_authentication_security_workspace_contract.py

djlint --check \
  app/templates/access/authentication_security/index.html \
  app/templates/access/authentication_security/partials/_page_content.html

python -m pytest -q -p no:cacheprovider \
  tests/access/authentication/test_mfa_policy_contract.py \
  tests/access/authentication/test_bot_protection_turnstile.py \
  tests/contracts/access/test_authentication_security_workspace_contract.py

python scripts/verify_sidebar_navigation_standard.py
python scripts/verify_access_final_lock.py
python scripts/verify_settings_final_lock.py

python -m pytest -q -p no:cacheprovider \
  tests/access/authentication \
  tests/contracts/access
```

Use existing Developer Check planner for additional impacted paths; no new standalone security-validation script is necessary.

## Browser / permission review

1. Sign in as authorized UAT administrator with `identity_providers.view`.
2. Navigate **Access → Authentication Security**. Verify Violet Hero, read-only status, responsive layout, sidebar active state and breadcrumbs.
3. Select Overview, Multi-Factor Authentication, Bot Protection and Session Security tabs. Verify normal GET URLs with `?tab=`, HTMX replacements, browser Back/Forward, keyboard focus, default/fallback routes and errors.
4. Confirm MFA is **Not Enabled**, Bot Protection is **Not Enabled**, Turnstile is **Not Configured**. No button can activate either. Session Security accurately states the existing single-login-generation and Remember Me behavior and leaves idle/absolute timeout unqualified.
5. Repeat desktop/mobile viewports, light/dark mode, keyboard/screen reader tab semantics.
6. With an account lacking `identity_providers.view`, verify the sidebar capability is absent and direct URL to `/access/authentication-security/` is denied server-side.
7. Retest one normal Local/LDAP UAT account login; confirm no CAPTCHA/MFA has silently become required and existing Activity Audit remains intact.
8. Do not submit any real TOTP secret, provider verification secret, recovery code, or personal browser cookie to chat/evidence.

## Evidence matrix

| Area | Expected | Status |
|---|---|---|
| MFA-01 policy unit matrix | Deterministic allow/challenge/enrollment; invalid fails closed | NOT RUN |
| BP-01 siteverify unit matrix | Fixed endpoint, hostname/action/time checks, rejects unknown provider/outage | NOT RUN |
| Admin workspace | Four read-only tabs, responsive/accessible | NOT RUN |
| Unauthorized access | Hidden navigation and HTTP deny | NOT RUN |
| Legacy authentication regression | No change to normal login/RBAC/remember-me/audit | NOT RUN |
| Full MFA TOTP challenge | **NOT IMPLEMENTED** (#3134) | BLOCKED |
| Provider registration and CAPTCHA login | **NOT IMPLEMENTED** (#3137) | BLOCKED |

Record operator outcome and exact SHA before marking focused UAT PASS. Do not equate source integration or focused test success with MFA/CAPTCHA production protection.

## Delivery

Issue branches → Draft PRs #3139/#3140/#3141 → reviewed holding integration → local QA/UAT → human acceptance. Official Developer Check, Full Admission, `kaori/staging`, main and release stay HOLD pending explicit approval.


## Supersession — full-cycle authentication UAT

This file is the original read-only source review. For the subsequent
policy-driven TOTP and live Turnstile implementation, use
`docs/operations/authentication-security-full-cycle-uat.md`.
Never mistake the earlier NOT IMPLEMENTED snapshot for current source state,
or mark full-cycle security UAT PASS before actual browser execution.
