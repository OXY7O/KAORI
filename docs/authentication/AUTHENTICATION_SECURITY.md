# Authentication security requirements

## Trust assumptions

- TLS terminates only at an approved reverse proxy or the application endpoint.
- `ProxyFix` counts exactly match trusted proxy hops; otherwise forwarded addresses are untrusted.
- PostgreSQL, Redis, and provider endpoints are on controlled networks.
- Secrets are delivered through deployment secret mechanisms, not committed configuration.
- System time is synchronized because session, OIDC, certificates, and audit chronology depend on it.

## Credential handling

- Local passwords are stored only as adaptive password hashes through Werkzeug's configured secure method.
- Plaintext credentials exist only for the request duration and are never copied to logs, audit metadata, exceptions, task queues, or notifications.
- LDAP bind secrets, OIDC client secrets, SAML keys, tokens, codes, assertions, and provider payloads follow the same rule.
- Password comparison and provider failures return normalized reason codes and generic messages.

## Session and cookie policy

- Rotate session state on every successful login.
- **Single active login generation per human account:** every successful Local Database, LDAP or browser SSO login advances `User.auth_session_version` through an atomic database UPDATE with RETURNING. Only the exact returned generation is attached to the login response; the prior browser/remember generations are invalid on their next authenticated request, across KAORI web instances. Concurrent successful logins cannot both retain valid generations.
- A non-secret random `auth_session_ref` correlates successful sign-in and sign-out Activity Audit events. It is **not** a bearer token, cookie value, device identifier or authentication input; audit never persists session cookies. Login audit records the authoritative actor/source and does not imply a revoked browser performed a sign-out.
- This control limits independently issued login sessions, **not** the number of humans operating a shared credential or users replaying a copied identical authenticated cookie. Individual human accounts, strong MFA and incident response remain mandatory; avoid describing this as physical-device or person binding.
- No per-session active-device registry/remote termination UI exists in this increment. Later scoped work can add active-session inventory and administrative revocation without replacing the generation admission guard.
- Use Secure, HttpOnly, SameSite=Lax cookies in production.
- Logout is a POST action protected by CSRF.
- Super-admin persistent sessions are disabled by default.
- Step-up authentication state is cleared on logout.
- Enable Flask-Login strong session protection unless compatibility testing proves otherwise.
- Define absolute and idle session timeouts before SSO activation; do not rely only on provider token lifetime.
- Disabling an enabled external Identity Provider revokes all KAORI sessions issued to its linked external-source user projections on their next request. A guarded provider-row lock and atomic session-generation increment keep disablement and revocation in one transaction. This applies to LDAP and browser SSO, without a live provider call on every page.
- Disabling blocks fresh provider authentication immediately after commit. Re-enabling permits new authentication but does **not** resurrect old cookies or remember-me sessions. A logout is not required to revoke them; currently in-flight requests are not retroactively stopped.
- Independent Local Database users (especially break-glass Super Admin) must remain unaffected. Audit reports the count of **linked identities** whose generations were changed, not a guessed number of browser sessions.

## Brute force and lockout

The current endpoint limiter is the first layer. Production must use Redis-backed shared rate-limit storage for multi-instance deployments. The next account-security increment should add durable counters and `locked_until` without revealing whether a username exists.

Recommended policy baseline for design review:

- per-IP and per-identity throttling;
- escalating delay after repeated failures;
- time-bound lockout rather than permanent automatic disable;
- administrator unlock with Activity Log;
- break-glass account alerts rather than easily triggered permanent lockout;
- metrics for failure spikes without username leakage.

## Error handling

User-visible failures must distinguish only actionable service availability from generic credential rejection. Detailed exceptions belong in restricted application logs with a request/correlation identifier. Login Activity stores a normalized reason code, not stack traces.

## External provider requirements

LDAP requires TLS certificate validation, bounded connect/read timeouts, safe search filters, controlled bind identity, and explicit attribute mapping. OIDC requires issuer discovery validation, exact redirect URI, state, nonce, PKCE where applicable, signature and claim validation, short-lived authorization state, and no token logging. SAML requires signed assertion validation, audience/recipient checks, replay prevention, trusted metadata, and strict XML security.

## Audit requirements

Record timestamp, attempted normalized username or external subject reference, provider, success/failure, safe reason code, proxy-normalized client address, user agent, and user ID when known. Never record passwords, tokens, assertions, raw LDAP responses, cookies, or secret configuration.


## MFA policy administration feedback and audit (#3208)

`Access → Authentication Security → Multi-Factor Authentication` uses the
existing KAORI Operational Toast pipeline for administrator policy saves. A
committed mode transition updates the policy, increments active user session
generations and stages immutable **MFA Policy Changed** actor/delta evidence
in the **same transaction**. After commit the admin's now-revoked
authentication session is explicitly cleared, **then** a success toast is
queued and the browser redirects to Login. The toast is intended to survive
on the Login layout; the old browser session and Remember Me token remain
invalid.

Saving the already-current policy must **not** revoke sessions or present a
false policy change. The action is recorded distinctly as
`mfa_policy_unchanged`, with previous/new mode values identical; a neutral
info toast returns to the MFA administrator tab. On database failure the
transaction rolls back and no successful transition may be shown or audited.
Both cases use the existing KAORI Operational Feedback builder to mark
the already-committed Activity Audit evidence in the toast; that marker
does **not** persist a duplicate event. A rollback/error uses transient
feedback without a false audit success indicator. Both cases must honor
CSRF, the `identity_providers.manage` permission and the enrolled local
recovery Super Admin prerequisite for mandatory modes.

The Activity Audit presentation treats `mfa_*` and `bot_*` events as
**Authentication Security controls** in Access, not as User Signed In events.
Immutable evidence retains actor snapshot, prior/new mode and the optional
opaque session correlation reference without TOTP seeds, recovery codes,
browser cookies, CAPTCHA tokens, or provider secrets.

This behavior uses existing notification-backed committed audit and
transient feedback primitives; no parallel toast/audit platform, new database
migration or additional MFA factor mechanism is introduced.


## TOTP enrollment object representation hardening (#3237)

Enrollment provisioning URIs contain the plaintext TOTP secret by protocol design and are transient sensitive output. The frozen `TotpEnrollment` structure must **never expose its encrypted_secret or provisioning_uri fields in its automatic Python representation**; both fields are `repr=False`. This mitigates accidental leakage into application logs, traces, test assertion output and exception representations. Authorized direct access to the provisioning URI for manual authenticator setup is unchanged.

This safeguard does **not** authorize logging a provisioning URI, storing it as permanent plaintext, or including it in Activity Audit metadata. Verify the existing `test_mfa_factor_primitives.py` proof that the URI still works for enrollment while `repr(enrollment)` exposes neither secret nor URI. Source-level hardening is not a substitute for Dev Container security and functional verification.


## Personal MFA self-service rejection feedback (#3251)

The existing `Settings → Account & Authentication → MFA` handler remains authoritative for CSRF, `login_fresh()`, local-password reauthentication, `begin`/`confirm`/`regenerate` dispatch, credential encryption and transaction. To make UAT failures actionable, only known server-owned `MfaVerificationError` reason strings are mapped to safe end-user explanations: stale sign-in → sign out/sign back in; invalid local password → retry current password; enrollment not started/expired → generate a new setup key; invalid OTP → check authenticator clock. Invalid CSRF has a separate refresh-and-retry message. Unknown exception details, credential values and TOTP seed/URI must **never** be echoed into the browser.

This improvement is about safe failure **observability**, not a claim that the reported failed Generate Setup Key was caused by a particular condition. Real Dev Container UAT must capture sanitized request status and displayed feedback without printing passwords, OTPs, provisioning URI or recovery codes. A successful `begin` response must preserve `Cache-Control: no-store`; actual factor activation still requires OTP confirmation. Database/encryption failure remains fail-closed and is not an MFA enrollment success.
