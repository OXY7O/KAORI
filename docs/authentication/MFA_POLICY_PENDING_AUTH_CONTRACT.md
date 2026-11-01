# MFA-01 — Policy & Pending Authentication Contract

Authority: #562 (MFA), #638 (Security), #641 (human/privileged access), #3121 (single-session generation), implementation #3133.

## Current state and activation boundary

`app/access/authentication/mfa/policy.py` is a **pure decision kernel**, not an active MFA challenge. No factor persistence, browser challenge, policy administration, session middleware, enrollment or provider mutation is introduced by MFA-01.

**MFA protection is NOT ENABLED merely because this module exists.** No login route calls the policy until MFA-02 provides trusted factor storage, bounded pending-auth state, verified proof, rollout safety and e2e UAT.

## Canonical assurance sequence

```text
Local / LDAP / OIDC / OAuth primary credential success
    → provider-neutral KAORI admission
    → committed effective MFA policy (fail closed if invalid)
    → verified factor enrollment status (never supplied by browser)
    → MFA policy decision:
        allow                → atomic single-login-generation issuance (#3121)
        challenge            → restricted pending-auth only (NOT login_user)
        enrollment_required  → restricted onboarding only (NOT login_user)
    → server-verified TOTP or one-time recovery code
    → recheck account active, provider status, RBAC role, fresh policy and factor state
    → commit login generation (#3121) ONCE, only after complete authentication
    → establish authenticated browser session; audit correlation
```

Never advance `auth_session_version` on **primary-auth-only success** if a second factor is required. Otherwise a malicious password-only attempt could evict the currently legitimate user.

The existing `login_required` and `permission_required` decorators MUST remain denied while pending. Pending state is short-lived, CSRF/session-bound, rate-limited, replay-resistant and isolated from normal login cookies and remember-me. A copied cookie or browser-provided `factor_verified` field is never accepted as proof. No raw OTP/recovery code, TOTP key, unbounded challenge input, credential, or secret may enter normal logging or Activity Audit.

## Policy behavior

| Policy | No enrolled factor | Verified enrolled factor |
|---|---|---|
| Disabled | Allow ordinary primary login | Allow ordinary primary login |
| Optional | Allow primary login | Require second-factor challenge |
| Required for privileged roles | Controlled enrollment if privileged, otherwise allow | Require challenge |
| Required for all users | Controlled enrollment | Require challenge |

`privileged` is supplied by current effective KAORI access classification (including local super-admin); never use an arbitrary role slug from a login form. An inactive user/role or disabled linked provider fails existing admission independently of MFA.

## Operational release gates

1. Approved encrypted TOTP secret and hashed single-use recovery code persistence (#3134), tested rotations/backup behavior.
2. Verified pending-auth expiration, CSRF, rate limit, forbidden direct-route bypass and replay resistance.
3. Safe last-local-super-admin recovery; no undocumented MFA bypass or forced unreviewed global rollout.
4. Event-specific audit (enrollment, success, failure, reset and policy changes), secret redaction, no implied upstream IdP MFA trust.
5. Local, LDAP and configured SSO browser UAT, remember-me/single-session regressions, quality/static/DAST, exact-SHA Human Acceptance.

Normal KAORI release admission is HOLD until operator authorization.
