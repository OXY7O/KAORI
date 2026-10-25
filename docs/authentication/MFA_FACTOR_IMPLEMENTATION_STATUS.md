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
