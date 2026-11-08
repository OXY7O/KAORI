# MFA-02 — Canonical TOTP / recovery implementation

Authority: #562, #3134, #3133, #3121.

KAORI now has a persisted, encrypted `AuthenticationMfaFactor` using the existing
`EncryptedText` key ring and a vetted `cryptography` RFC 6238 TOTP verifier.
The authoritative runtime is `app/access/authentication/mfa/service.py`.
It stores recovery codes as Werkzeug password hashes and consumes an unused
code or time-step under an exclusive database row lock before minting the
single-active-login session generation.

The older standalone factor helpers remain as a compatibility facade, using
the **same** `cryptography` TOTP implementation. `pyotp` has been removed
from `requirements/base.txt` because the active runtime no longer requires
it. This eliminates a duplicate crypto dependency and resolves the observed
Dev Container `ModuleNotFoundError` for `pyotp`.

## Flow and status

- Settings → Account & Authentication → MFA enrolls an individual factor and
  verifies an OTP before activation. Manual setup key is shown only once.
- After primary Local, LDAP or browser SSO verification, a required enrolled
  factor triggers a restricted `/auth/mfa` challenge before login generation
  issuance. Unenrolled required accounts use the restricted enrollment route.
- A successful OTP or single-use recovery code completes authentication; a
  failed attempt cannot replace a valid existing browser session.
- Admin MFA modes: Disabled, Optional, Required Privileged, Required All.
  Changing effective mode revokes previously issued browser/remember sessions.
- Active Local Database super-admin recovery authority must be enrolled before
  enabling mandatory MFA. Operating recovery must remain documented.
- MFA is **functionally implemented in source**, but security and human UAT
  remain **NOT PASS** until tested at the exact SHA with PostgreSQL, browser,
  provider-disable and break-glass evidence.

No third-party OTP SaaS is needed; authenticator apps are interoperable TOTP
clients, not configured KAORI Identity Providers.

## Required QA

```bash
ruff check app/access/authentication/mfa tests/access/authentication/test_mfa_factor_primitives.py
ruff format --check app/access/authentication/mfa tests/access/authentication/test_mfa_factor_primitives.py
python -m pytest -q -p no:cacheprovider tests/access/authentication/test_mfa_policy_contract.py tests/access/authentication/test_mfa_factor_primitives.py
```

Official admission remains HOLD by operator instruction.

## Challenge-screen presentation checkpoint — centered Verify Your Sign In (#3290, 2026-10-26)

**Source-only UX scope:** `app/templates/access/authentication/mfa_challenge.html` now centers the shield, short MFA context, heading and two concise instructions, followed by the unchanged server-owned Verification Code / Verify & Sign In form and Start a New Sign In action. No new QR scanner, segmented OTP input, external provider, persistence or authentication control is introduced. The same field supports a valid six-digit authenticator code or unused recovery code.

**Dev Container validation:**
```bash
ruff check tests/contracts/access/authentication/test_mfa_challenge_visual_contract.py
ruff format --check tests/contracts/access/authentication/test_mfa_challenge_visual_contract.py
djlint --check app/templates/access/authentication/mfa_challenge.html
python -m pytest -q -p no:cacheprovider tests/contracts/access/authentication/test_mfa_challenge_visual_contract.py tests/contracts/access/authentication/test_authentication_surface_final_lock_contract.py tests/access/authentication/test_mfa_policy_contract.py
python scripts/verify_authentication_surface_final_lock.py
```
Browser UAT must compare 1440/1280 desktop, 390/360 mobile, keyboard navigation and both themes. With an authorized disposable account and an enabled enrolled factor, verify invalid/expired/replayed TOTP and consumed recovery codes fail without authentication, while valid TOTP or unused recovery code completes the previously pending login and audit once. Preserve rate-limits, attempt expiry, CSRF and Start a New Sign In behavior; never attach actual TOTP or recovery codes. **Runtime QA and Human Acceptance are pending** until evidence is collected at the exact holding SHA; official admission stays on HOLD.
