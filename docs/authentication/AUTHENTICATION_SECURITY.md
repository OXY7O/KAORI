# Authentication security requirements

## Trust assumptions

- TLS terminates only at an approved reverse proxy or the application endpoint.
- `ProxyFix` counts exactly match trusted proxy hops; otherwise forwarded addresses are untrusted.
- PostgreSQL, Redis, and provider endpoints are on controlled networks.
- Secrets are delivered through deployment secret mechanisms, not committed configuration.
- System time is synchronized because session, OIDC, certificates, and audit chronology depend on it.

## Credential handling

- Local passwords are stored only as adaptive password hashes through Werkzeug's configured secure method.
- New Local Database passwords use the existing 12–1024-character shared validator, a case-insensitive bounded default/common-password blocklist (including values meeting minimum length), and canonical length guidance on Account, user creation, and reset. The list is not a comprehensive breach corpus; no credential is sent to an external service. Existing hashes are not invalidated by the blocklist. A minimum-length change or compromised-password screening requires separate policy review and qualification across local provisioning, reset and break-glass.
- Plaintext credentials exist only for the request duration and are never copied to logs, audit metadata, exceptions, task queues, or notifications.
- LDAP bind secrets, OIDC client secrets, SAML keys, tokens, codes, assertions, and provider payloads follow the same rule.
- Password comparison and provider failures return normalized reason codes and generic messages.

## Session and cookie policy

- Rotate session state on every successful login.
- **Single active login generation per human account:** every successful Local Database, LDAP or browser SSO login advances `User.auth_session_version` through an atomic database UPDATE with RETURNING. Only the exact returned generation is attached to the login response; the prior browser/remember generations are invalid on their next authenticated request, across KAORI web instances. Concurrent successful logins cannot both retain valid generations.
- A non-secret random `auth_session_ref` correlates successful sign-in, sign-out and system-owned session-expiry Activity Audit events. It is **not** a bearer token, cookie value, device identifier or authentication input; audit never persists session cookies. Login audit records the authoritative actor/source and does not imply a revoked browser performed a sign-out.
- This control limits independently issued login sessions, **not** the number of humans operating a shared credential or users replaying a copied identical authenticated cookie. Individual human accounts, strong MFA and incident response remain mandatory; avoid describing this as physical-device or person binding.
- No per-session active-device registry/remote termination UI exists in this increment. Later scoped work can add active-session inventory and administrative revocation without replacing the generation admission guard.
- Use Secure, HttpOnly, SameSite=Lax cookies in production.
- Logout is a POST action protected by CSRF.
- Privileged human accounts (Admin-level and Local Database Super Admin) never receive Remember Me persistence. Ordinary Remember Me is configurable and only restores the still-valid original generation within both server deadlines. The legacy `AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME` environment flag is no longer an override.
- Step-up authentication state is cleared on logout.
- Enable Flask-Login strong session protection unless compatibility testing proves otherwise.
- **Session lifecycle policy (#5280 / #5282, 2026-11-28):** default privileged idle 15 minutes / absolute 4 hours; ordinary idle 30 minutes / absolute 8 hours; default warning 2 minutes. The existing authentication security policy owns these values. Privileged limits may not exceed ordinary limits; warning must precede idle expiration. All Local, LDAP and browser SSO sessions use the same KAORI server-side authority, never provider token lifetime.
- Successful final authentication atomically issues the generation and both UTC timestamps. Each protected admission checks the same committed issuance/activity state and rejects missing, malformed, stale or expired state. Existing cookies without the new timestamps require a fresh sign-in. Password-change continuity must not reset absolute age; new authentication resets both clocks. Self-service replacement locks the admitted user row against the presented generation and verified hash, then commits the replacement, generation and security audit together. The browser is pinned to that exact committed generation; staged evidence is not emitted before commit. Concurrent stale credential proof at final login issuance remains a separate qualification boundary. Browser close and restoration are not trusted revocation boundaries.
- Only the explicit CSRF-protected authenticated activity endpoint may advance idle activity. Passive status, Notification Deck polling, HTMX background refresh and other automatic requests never extend it. Exact-generation conditional writes protect concurrent new logins and expiry/refresh races. Expiry revocation and system-owned audit commit together; logout revokes the presented generation and commits its audit before claiming server-side termination. No cookie or credential values enter evidence.
- If the authentication database or policy is unavailable, protected admission fails closed. Keep the no-active-device-inventory boundary. The signed cookie remains a bearer credential within its valid generation; this does not introduce device binding.
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


## Local QR provisioning and Operational Toast for personal MFA (#3261)

Personal MFA setup in `Settings → Account & Authentication → Multi-Factor Authentication` offers the same **one-time** TOTP provisioning material in two formats after `begin_mfa_enrollment` has authenticated the current user and atomically committed the pending factor and audit event:

- **Scan QR Code:** rendered locally with pinned Python `qrcode==8.2` and Pillow as a base64-encoded PNG data URI in the HTML response. The encoded content is the canonical `otpauth://totp` provisioning URI generated by `mfa.factors.totp_provisioning_uri`, with the authenticated account label. It is never sent to an external QR API, constructed as an HTTP URL, passed via request querystring, written to a log, session, Activity Audit, database column, or Notification Deck. The existing CSP allows `img-src data:`.
- **Manual Setup Key:** the same sensitive TOTP seed remains a fallback in the same one-time response. QR is an alternative presentation, not another enrollment factor/provider. The user must still confirm a valid fresh six-digit OTP to enable MFA.

The successful POST response is protected with `Cache-Control: no-store`, `Pragma: no-cache`, and `Referrer-Policy: no-referrer`. Do not capture or forward QR images or manual keys in human UAT screenshots. Reissue the pending secret if previously disclosed in a screenshot or ticket, and use only the new key.

The UI uses existing **KAORI Operational Toast** behavior for personal MFA `begin`, `confirm`, `regenerate`, and safe rejection messages, including full-page queued feedback and HTMX OOB rendering. Successful factor service mutations already stage and commit their audit events. The toast's `activity_audit_saved=True` references that **existing** evidence; no duplicate event and no Notification Deck notification are created. Errors cannot claim a successful audit. The previous wide inline generic info banner is removed. Factor authority and transaction logic remain unchanged.

Install updated `requirements/base.txt` in Dev Containers before opening the application. Dependency addition does not require a database migration. Use the existing account MFA route and validate browser behavior under CSP, keyboard navigation and both themes.

## Bot Protection administration UX and activation authority (#3299, 2026-10-26)

The Access Authentication Security **Bot Protection** tab uses a committed KAORI policy summary and three status tiles, the existing Cloudflare Turnstile registry, and a manager-gated `Protection Configuration` form. Its right-side `Activation & Safety` explanation is guidance, **not** a newly implemented workflow engine or evidence of readiness. The provider remains externally authoritative for Siteverify; KAORI owns stored configuration, normalized result, activation policy, committed event and audit.

Only `Disabled` and `Always` are implemented. The existing `save_bot_policy` endpoint requires CSRF, admitted `cloudflare_turnstile`, impact acknowledgment, complete validated credentials, and a successful unexpired test of the unchanged configuration before enabling Always. The `test_bot_provider` endpoint requires a real browser-issued Turnstile token verified server-side under expected hostname/action and commits its own sanitized verification evidence; modifying the saved configuration invalidates older test evidence. Provider keys do not prove live availability and `bot_tested_at` alone must not be presented as provider health. Viewers receive a read-only summary; user-visible UI never redisplays the stored secret.

Turnstile challenge during sign-in applies only when the committed policy requires it, precedes credential or SSO handoff, and fails closed when verification fails or Cloudflare is unreachable. Recovery must be independently available before enforcement. No fake Adaptive policy, suspicion toggle, provider selector, or extra secret persistence is added by the layout change. Local/LDAP/SSO security and DAST/UAT remain required before human acceptance.

## Exact-generation MFA mutations and atomic recovery rotation (#5342)

Begin, confirmation, challenge consumption and recovery-code rotation use one account-first, factor-second row-lock order. The service validates the originally presented authenticated or pending generation and current source/lifecycle/role; authenticated mutations additionally check the committed idle and absolute session deadlines. Factor state is refreshed after lock, and a rejection rolls back rather than retaining locks or partial changes. Personal regeneration consumes the submitted OTP or recovery proof, stages its security audit, replaces the recovery hashes and stages rotation evidence in one transaction. No one-time codes or success feedback are returned before commit; failure does not consume proof independently of the replacement. Local password and CSRF checks remain unchanged; SQL/encryption exception details are not logged by the personal handler. Pending enrollment binding across generations, final issuance coupling, explicit cancel/replacement and recent primary reauthentication remain separate lifecycle qualification under #5322. Source controls require actual PostgreSQL and browser UAT.

## Pending MFA ownership and cancellation (#5346)

An inactive TOTP setup stores its originating authentication generation and authenticated versus pending-login context alongside the encrypted seed and expiry. Confirmation and explicit cancellation require the exact context under the existing account/factor locks. Legacy unbound setup or a changed generation is not valid for confirmation and must be regenerated; active enrolled factors are unchanged. Cancellation deletes only the matching inactive row and commits the security event in the same transaction; required enrollment cancellation returns to sign-in without issuing any authenticated cookie. The additive migration does not infer historical ownership. Downgrade removes inactive setup material before dropping the guard columns, preserving active factors and recovery hashes. Provider credentials remain external; this is not device binding or an authenticator replacement workflow. Actual migration, PostgreSQL concurrency, browser and provider qualification remain required.

## Personal factor assurance boundary (#5351)

Flask-Login fresh state is necessary but is not proof of time-bounded primary reauthentication. For authenticated personal begin and recovery rotation, verify a Local Database current password against the freshly locked authoritative account row; the password is never persisted in a session or audit. Existing external-owned enrollment and recovery rotation require committed KAORI admission less than 300 seconds old (existing pending-MFA horizon), plus existing fresh state and applicable factor proof. Missing or future issuance time is rejected; activity refresh does not extend this window. Confirmation relies on the generation/context-owned pending setup and its ten-minute deadline. Cancellation does not require a new primary credential. Required enrollment after primary authentication retains the pending-flow contract.

A recent KAORI admission is **not** evidence of recent upstream credential verification. Google OIDC currently uses select_account without a verified auth_time contract; GitHub OAuth callback has no verified primary credential age. LDAP explicit bind is a potential provider-owned proof path but needs separately qualified binding. The strict primary assurance helper therefore permits only verified Local Database password and denies external sources until independent provider proof is implemented; no replacement action is introduced in this increment. No provider password is submitted to the personal Settings handler. The five-minute threshold is a conservative derived design choice, not an independently approved organization-wide reauthentication policy. Exact-candidate runtime qualification remains required.

## Governed Local Database authenticator replacement (#5357)

Existing enrolled Local Database users can start replacement only after strict password verification and consumption of an active TOTP or recovery proof under account/factor locks. A separate encrypted seed is stored with the originating generation and a five-minute expiry; the active TOTP remains authoritative, and a submitted recovery proof is consumed once. Confirmation verifies the new OTP, rotates the seed and recovery hashes, advances the session generation and clears pending state with the security audit in one transaction. The initiating browser receives only that committed generation, with original idle/absolute timestamps preserved and Remember Me cleared. A concurrent later sign-in cannot be adopted. Cancellation removes only the pending replacement. Recovery regeneration invalidates pending replacement in its own transaction. An expired/stale setup cannot be confirmed and must be restarted. External replacement is not available until provider-owned strict reauthentication is qualified. The migration adds nullable encrypted replacement fields; downgrade discards pending replacement but preserves the active factor. Existing MFA policy and required login enrollment are unchanged. Source implementation is not runtime qualification; actual PostgreSQL concurrency, migration and browser/provider UAT remain required.

## Atomic pending MFA admission (#5361)

Pending challenge proof consumption or required enrollment activation, exact original generation issuance (including session timestamps), and canonical successful-login audit now share a single account-first/factor-second database transaction. Re-evaluate source, current MFA policy, factor state and finite pending deadline under locks; verify expiry again after proof work. No browser session is established before commit. The transaction returns its exact generation, Remember Me decision, opaque login audit reference, and (only for enrollment) one-time recovery codes. The route pins that generation and reference without a second success audit. The committed audit asserts server admission, not HTTP delivery: network failure or post-commit browser/session failure cannot be rolled back by a database transaction. In that case the user must reauthenticate; if enrollment recovery codes were not delivered, use the verified authenticator and governed regeneration/recovery. This increment does not claim atomic HTTP delivery, upstream credential reauthentication, or protection against every external-provider disable race. Runtime PostgreSQL, concurrency and browser/provider qualification remain required.

## External provider proof fencing (#5365)

Every committed provider registry update advances a monotonic authentication revision under the existing provider-row lock. LDAP bind captures the exact instance/revision/link before remote verification; browser SSO binds the authorization flow to the provider revision and revalidates it before identity projection. External final issuance locks the provider before account/factor operations, checks the enabled instance, exact revision, source and linked user, and denies legacy/unbound proofs. Pending MFA retains only non-secret provider/revision/link identifiers. Disable and issuance serialize on the same provider lock; disabling after issuance revokes linked generations, while disabling before issuance or disable/re-enable rejects old proof. Configuration-only updates also invalidate in-flight proofs conservatively, not existing admitted sessions. This is KAORI provider registry assurance, not evidence of fresh upstream primary credentials, nor a claim that remote provider-side credential revocation is detected in real time. Strict LDAP/SSO replacement remains unavailable until qualified. Migration is additive; old pending external flows require restart. Actual concurrent PostgreSQL and provider/browser tests remain required.

The external proof fence also applies before required pending setup begin/cancel. Provider and exact link rows are locked before the user/factor transaction; concurrent link modifications must not pass the same proof fence. Upgrade/downgrade requires a quiesced authentication deployment: do not mix old/new workers or reuse signed pre-downgrade flow cookies. The revision is intentionally a conservative registry-wide epoch, not upstream authentication time.

## Strict LDAP primary reauthentication for replacement (#5374)

An enrolled LDAP-owned account may start replacement through the existing self-service workflow only with exactly one provisioned LDAP identity link, enabled provider, certificate-verified LDAPS/StartTLS and successful explicit user bind followed by stable-subject BASE readback on the same connection (no referrals). The directory remains the password authority; no local comparison, password persistence or username fallback. Read-only capability discovery does not contact LDAP. Capture provider revision, link and stable identity before remote verification, then revalidate under provider/link locks before the admitted account and factor locks. A five-minute request-local proof is persisted with pending replacement as non-secret provider binding metadata, never the password; confirm revalidates revision, identity and expiry before atomic swap. Cancel may discard only the owned pending replacement. Scoped replacement-start rate limiting reuses the credential login limit. LDAP transport/attribute ACL failure, ambiguity and stale provider evidence fail closed. Google/GitHub still unavailable for strict replacement. Existing ordinary enrollment and recovery policy is unchanged. Actual provider bind/TLS/ACL, concurrency and browser qualification required before acceptance.

Replacement audit records the method (local current password or linked LDAP bind), and for LDAP only the provider instance, revision and link identifiers; no stable subject, DN, password or factor material is included in audit. The five-minute clock starts before remote bind, so slow provider verification cannot extend assurance lifetime. The stable subject on the current account must match the linked identity before and after bind. The LDAP feature requires qualification of stable-attribute visibility using the user's own directory permissions.

## Browser SSO strict reauthentication capability decision (#5376)

Assessment 2026-11-28 against the current Google OIDC and GitHub OAuth adapters and official provider references. Google supports optional signed authentication-time evidence (`auth_time`) when requested and enabled in settings, but explicitly does not support Google Account reauthentication requests. The existing Google adapter performs account selection and validates signed identity/nonce, not upstream authentication recency. OIDC Core defines `max_age` and `prompt=login`, but their presence in the standard is not proof Google supports them. GitHub's OAuth authorization flow supports account selection and authorization and returns an access token for identity lookup; the reviewed contract does not provide a verified primary authentication timestamp or supported strict reauthentication mechanism. A new callback, token issuance time, consent, account picker, KAORI freshness, session generation and registry revision are not substitutes for strict primary proof.

Decision: keep strict browser SSO replacement unavailable; no password input, no mutation form, no direct begin/confirm/cancel, and no fall back to Local/LDAP. Existing SSO login, enrollment and recovery regeneration policy is unchanged. Use existing governed administrator recovery under Access authority (not an automatic reset or policy bypass). A future Google recent-authentication proposal may evaluate a separately enabled signed `auth_time` claim and risk-based assurance policy, but requires explicit approval because it is not an on-demand reauthentication mechanism. Any future implementation must bind issuer/audience/nonce/immutable subject, provider instance/revision, admitted account/generation, bounded timestamp and one-use action evidence; deny absent, stale, future or malformed claims. GitHub requires a documented independently verifiable provider-owned assurance mechanism before self-service replacement can be enabled. No live provider proof or runtime UAT was performed in this increment.

References (reviewed 2026-11-28): [Google Security bundle](https://developers.google.com/identity/siwg/security-bundle), [Google OIDC API reference](https://developers.google.com/identity/openid-connect/reference), [GitHub OAuth app authorization](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps), [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0.html).

Source review also corrected #5374's LDAP source/adapter mismatch: the canonical registry and identity foundation migration use `ldap_directory` for provider/account ownership and `ldap` for the adapter. Replacement capability, binding query, provider lock and UI now use the canonical source key; the obsolete source alias is not accepted. The correction is included in #5376, not a new provider taxonomy or data migration.
