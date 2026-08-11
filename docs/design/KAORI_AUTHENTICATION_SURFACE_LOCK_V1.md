# KAORI Authentication Surface Lock v1

Status: **FINAL LOCKED**  
Date: 2026-08-11

## Scope

This lock covers the unauthenticated KAORI authentication presentation surface:

- Login
- Database Setup Required
- `layouts/auth.html`
- Auth-specific first-party CSS/JavaScript required by those surfaces

It does not redesign identity-provider administration, User Management, Roles & Access, Account & Authentication Settings, or provider protocol implementations.

## Locked Presentation Contract

1. Login remains the approved compact split-screen design optimized for a 14-inch laptop.
2. KAORI Violet remains the primary brand/accent language and light/dark mode remains supported.
3. The pre-authentication brand panel stays provider-neutral; it must not reveal enabled internal workspaces, account state, roles, or provider-specific operational details.
4. Username/password controls remain 44 px high with visible labels, autocomplete metadata, CSRF ownership, accessible password visibility control, and a clearly labeled Remember Me control.
5. SSO actions are rendered only for enabled browser providers and propagate only the server-sanitized internal `next` target.
6. Login feedback keeps semantic success/error roles and an `aria-live` region.
7. Database readiness fails closed to the Database Setup Required surface with operator-safe initialization guidance.
8. Auth templates use canonical typography tokens: no arbitrary text sizes/tracking, no `font-extrabold`, no presentation-only uppercase utilities, and no inline DOM event handlers.
9. Password/theme interaction runtime is owned by `app/static/js/auth_login.js`; only the pre-paint theme bootstrap remains inline to prevent theme flash.

## Locked Security Contract

- Login is rate-limited and Flask-WTF owns CSRF validation.
- Credential failures remain provider/role neutral to avoid account-state disclosure.
- Post-login and SSO callback redirects accept only same-origin absolute paths.
- Successful authentication rotates session state before retaining authentication ownership.
- Logout is POST-only, authenticated, and preserves remember-cookie revocation.
- Remember Me defaults to 7 days, is bounded to 1–30 days, and remains default-deny for `super_admin` unless explicitly enabled.
- Production session and remember cookies remain Secure, HttpOnly, and SameSite=Lax.
- SSO state is fingerprinted, nonce is used when required, and the browser flow is TTL bounded.
- Failed authentication may identify a target account for evidence but never claims that target as the authenticated actor.

## Release Evidence

| Layer | Evidence |
| --- | --- |
| Static Quality | `verify_authentication_surface_final_lock.py`, Ruff, djLint, Pyright, UI debt guards, JS syntax |
| Contract | `tests/contracts/auth/` |
| Unit | `tests/unit/auth/test_auth_session_policy.py` |
| Functional | `tests/auth/test_login_characterization.py` |
| Security Regression | `tests/security/auth/test_authentication_security.py` |
| Rendering/UI | `tests/rendering/auth/test_authentication_rendering.py` |
| E2E Smoke | `tests/e2e/auth/test_authentication_smoke.py` |
| Integration | **N/A** — this presentation lock adds no provider, persistence, LDAP, OAuth/OIDC, or external-runtime integration boundary |

Future Authentication Surface work requires a concrete defect, security requirement, or approved product change. Cosmetic redesign alone does not reopen this baseline.
